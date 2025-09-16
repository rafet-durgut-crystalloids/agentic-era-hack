"""Tools used by the database query agent (BigQuery + NL2SQL orchestration)."""

from __future__ import annotations
import datetime
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from google.cloud import bigquery
from google.genai import Client
from google.adk.tools import ToolContext

from ....data_analysis.utils.utils import get_env_var

# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------
LOGGER = logging.getLogger(__name__)
if not LOGGER.handlers:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

# ------------------------------------------------------------------------------
# Environment / Globals
# ------------------------------------------------------------------------------
DATA_PROJECT_ID: Optional[str] = os.getenv("BQ_DATA_PROJECT_ID")
COMPUTE_PROJECT_ID: Optional[str] = os.getenv("BQ_COMPUTE_PROJECT_ID")
VERTEX_PROJECT_ID: Optional[str] = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION: Optional[str] = os.getenv("GOOGLE_CLOUD_LOCATION")

# Max rows cap for NL2SQL-generated queries
MAX_NUM_ROWS: int = int(os.getenv("NL2SQL_MAX_ROWS", "80"))

# Disallowed DML/DDL ops for validation (read-only enforcement)
DISALLOWED_DML_RE = re.compile(
    r"(?i)\b(update|delete|drop|insert|create|alter|truncate|merge)\b"
)

# Clients (lazy singletons)
_llm_client: Optional[Client] = None
_bq_client: Optional[bigquery.Client] = None

# Database settings cache
_database_settings: Optional[Dict[str, Any]] = None


# ------------------------------------------------------------------------------
# Client accessors
# ------------------------------------------------------------------------------
def get_llm_client() -> Client:
    """Return (and memoize) a Google GenAI client for Vertex."""
    global _llm_client
    if _llm_client is None:
        LOGGER.info(
            "Initializing GenAI client (vertexai=True, project=%s, location=%s)",
            VERTEX_PROJECT_ID,
            LOCATION,
        )
        _llm_client = Client(vertexai=True, project=VERTEX_PROJECT_ID, location=LOCATION)
    return _llm_client


def get_bq_client() -> bigquery.Client:
    """Return (and memoize) a BigQuery client using the compute project."""
    global _bq_client
    if _bq_client is None:
        compute_project = get_env_var("BQ_COMPUTE_PROJECT_ID")
        LOGGER.info("Creating BigQuery client (project=%s)", compute_project)
        _bq_client = bigquery.Client(project=compute_project)
    return _bq_client


# ------------------------------------------------------------------------------
# Database settings (schema cache)
# ------------------------------------------------------------------------------
def get_database_settings() -> Dict[str, Any]:
    """Get cached database settings (project, dataset, DDL schema)."""
    global _database_settings
    if _database_settings is None:
        _database_settings = update_database_settings()
    return _database_settings


def update_database_settings() -> Dict[str, Any]:
    """Refresh database settings from BigQuery (rebuild DDL schema snapshot)."""
    LOGGER.info("Updating database settings (rebuilding DDL schema snapshot)")
    ddl_schema = get_bigquery_schema(
        dataset_id=get_env_var("BQ_DATASET_ID"),
        data_project_id=get_env_var("BQ_DATA_PROJECT_ID"),
        client=get_bq_client(),
        compute_project_id=get_env_var("BQ_COMPUTE_PROJECT_ID"),
    )
    settings = {
        "bq_project_id": get_env_var("BQ_DATA_PROJECT_ID"),
        "bq_dataset_id": get_env_var("BQ_DATASET_ID"),
        "bq_ddl_schema": ddl_schema,
    }
    LOGGER.debug("Database settings updated: keys=%s", list(settings.keys()))
    return settings


# ------------------------------------------------------------------------------
# BigQuery schema → DDL (with sample rows)
# ------------------------------------------------------------------------------
def get_bigquery_schema(
    dataset_id: str,
    data_project_id: str,
    client: Optional[bigquery.Client] = None,
    compute_project_id: Optional[str] = None,
) -> str:
    """Retrieve schema and generate DDL (with sample inserts) for a dataset."""
    if client is None:
        LOGGER.info("No BigQuery client provided; creating with compute project")
        client = bigquery.Client(project=compute_project_id)

    dataset_ref = bigquery.DatasetReference(data_project_id, dataset_id)
    ddl_statements: List[str] = []

    info_schema_query = f"""
        SELECT table_name
        FROM `{data_project_id}.{dataset_id}.INFORMATION_SCHEMA.TABLES`
    """
    LOGGER.debug("Schema discovery query:\n%s", info_schema_query)
    query_job = client.query(info_schema_query)

    for row in query_job.result():
        table_ref = dataset_ref.table(row.table_name)
        table_obj = client.get_table(table_ref)
        LOGGER.info("Found %s: %s", table_obj.table_type, table_ref.path)

        if table_obj.table_type == "VIEW":
            view_query = table_obj.view_query
            ddl_statements.append(
                f"CREATE OR REPLACE VIEW `{table_ref}` AS\n{view_query};\n"
            )
            continue

        if table_obj.table_type == "EXTERNAL":
            _append_external_iceberg_ddl_if_applicable(ddl_statements, table_obj)
            # Skip DDL for other external types (keeps things concise)
            continue

        if table_obj.table_type == "TABLE":
            ddl_statements.append(_ddl_for_table_with_samples(client, table_obj))
            continue

        # Skip other types: MATERIALIZED_VIEW, SNAPSHOT, etc.

    return "".join(ddl_statements)


def _append_external_iceberg_ddl_if_applicable(
    ddl_statements: List[str], table_obj: bigquery.Table
) -> None:
    cfg = table_obj.external_data_configuration
    if cfg and cfg.source_format == "ICEBERG":
        uris = ",\n    ".join(f"'{u}'" for u in cfg.source_uris)
        cols = []
        for field in table_obj.schema:
            col_type = f"ARRAY<{field.field_type}>" if field.mode == "REPEATED" else field.field_type
            cols.append(f"  `{field.name}` {col_type}")
        cols_str = ",\n".join(cols)
        ddl_statements.append(
            f"""CREATE EXTERNAL TABLE `{table_obj.reference}` (
{cols_str}
)
WITH CONNECTION `{cfg.connection_id}`
OPTIONS (
  uris = [{uris}],
  format = 'ICEBERG'
);\n"""
        )


def _ddl_for_table_with_samples(client: bigquery.Client, table_obj: bigquery.Table) -> str:
    # Column definitions with descriptions
    cols = []
    for field in table_obj.schema:
        col_type = f"ARRAY<{field.field_type}>" if field.mode == "REPEATED" else field.field_type
        col_def = f"  `{field.name}` {col_type}"
        if field.description:
            col_def += " OPTIONS(description='{}')".format(
                field.description.replace("'", "''")
            )
        cols.append(col_def)
    ddl = f"CREATE OR REPLACE TABLE `{table_obj.reference}` (\n{',\n'.join(cols)}\n);\n"

    # Sample rows (best-effort; ok if empty/fails)
    try:
        sample_query = f"SELECT * FROM `{table_obj.reference}` LIMIT 5"
        LOGGER.debug("Sampling query: %s", sample_query)
        df = client.query(sample_query).to_dataframe()
        if not df.empty:
            ddl += f"-- Example values for table `{table_obj.reference}`:\n"
            for _, r in df.iterrows():
                values = ", ".join(_serialize_value_for_sql(v) for v in r.values)
                ddl += f"INSERT INTO `{table_obj.reference}` VALUES ({values});\n"
        ddl += "\n"
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning(
            "Sample retrieval failed for %s: %s", table_obj.reference.path, exc
        )
        ddl += f"-- NOTE: Could not retrieve sample rows for table {table_obj.reference.path}.\n\n"
    return ddl


# ------------------------------------------------------------------------------
# NL2SQL prompt + generation
# ------------------------------------------------------------------------------
def _build_nl2sql_prompt(ddl_schema: str, question: str, max_rows: int) -> str:
    """Construct the NL2SQL prompt (same logic, refreshed wording)."""
    prompt_template = """
You are a BigQuery SQL specialist. Given a natural-language request and the database schema below, produce a **GoogleSQL** query that answers the question.

Rules of engagement:
- **Fully qualified names**: Always reference tables with backticks and full paths: `project.dataset.table`.
- **Minimal joins**: Join only what’s necessary. Ensure join columns share the same data type.
- **Aggregations**: Every non-aggregated SELECT column must appear in GROUP BY.
- **Syntax correctness**: Use valid GoogleSQL. Alias with `AS` where helpful; wrap subqueries/UNIONs in parentheses.
- **Column discipline**: Use only columns that exist in the provided schema, and only under their rightful tables.
- **Filtering**: Apply appropriate WHERE/HAVING filters to avoid excessive row counts.
- **Row cap**: Return fewer than {MAX_ROWS} rows (add a LIMIT if needed).

Schema (tables and sample rows): {SCHEMA}
User question: {QUESTION}

Think step-by-step and return **only** the SQL (no prose).
""".strip()

    return (
        prompt_template.replace("{MAX_ROWS}", str(max_rows))
        .replace("{SCHEMA}", ddl_schema)
        .replace("{QUESTION}", question)
    )


def _call_nl2sql_llm(prompt: str) -> str:
    """Call the model to generate SQL; strip code fences."""
    model_name = os.getenv("GENERIC_MODEL")
    client = get_llm_client()
    LOGGER.info("NL2SQL: generating with model=%s", model_name)
    t0 = time.time()
    resp = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config={"temperature": 0.1},
    )
    elapsed = (time.time() - t0) * 1000.0
    LOGGER.info("NL2SQL: generation completed in %.1f ms", elapsed)

    sql_text = (resp.text or "").strip()
    # Remove markdown fences if present
    sql_text = sql_text.replace("```sql", "").replace("```", "").strip()
    LOGGER.debug("NL2SQL draft (first 200 chars): %s", sql_text[:200])
    return sql_text


def initial_bq_nl2sql(question: str, tool_context: ToolContext) -> str:
    """Generate an initial SQL query from a natural language question."""
    LOGGER.info("NL2SQL: building prompt for question")
    ddl_schema = tool_context.state["database_settings"]["bq_ddl_schema"]
    prompt = _build_nl2sql_prompt(ddl_schema, question, MAX_NUM_ROWS)
    sql = _call_nl2sql_llm(prompt)

    tool_context.state["sql_query"] = sql
    LOGGER.info("NL2SQL: draft SQL stored in tool_context.state['sql_query']")
    return sql


# ------------------------------------------------------------------------------
# Validation helpers
# ------------------------------------------------------------------------------
def _cleanup_sql(sql_string: str, max_rows: int) -> str:
    """Normalize escapes/newlines; ensure a LIMIT exists."""
    cleaned = (
        sql_string.replace('\\"', '"')
        .replace("\\\n", "\n")
        .replace("\\'", "'")
        .replace("\\n", "\n")
        .strip()
    )
    if "limit" not in cleaned.lower():
        cleaned += f" LIMIT {max_rows}"
    return cleaned


def _is_disallowed_dml(sql_string: str) -> bool:
    return bool(DISALLOWED_DML_RE.search(sql_string))


def _format_bq_rows(results: bigquery.table.RowIterator, max_rows: int) -> List[Dict[str, Any]]:
    """Convert BQ results to JSON-serializable rows (date-friendly)."""
    rows: List[Dict[str, Any]] = []
    for row in results:
        formatted = {}
        for key, value in row.items():
            if isinstance(value, datetime.date):
                formatted[key] = value.strftime("%Y-%m-%d")
            else:
                formatted[key] = value
        rows.append(formatted)
        if len(rows) >= max_rows:
            break
    return rows


def run_bigquery_validation(sql_string: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Validate a BigQuery query (read-only). Stores first rows to tool_context.state["query_result"].
    Returns:
      {
        "query_result": List[Dict] | None,
        "error_message": str | None
      }
    """
    LOGGER.info("Validation: starting")
    LOGGER.debug("Validation: original SQL:\n%s", sql_string)

    final_result: Dict[str, Any] = {"query_result": None, "error_message": None}

    # Disallow DML/DDL (read-only)
    if _is_disallowed_dml(sql_string):
        final_result["error_message"] = "Invalid SQL: Contains disallowed DML/DDL operations."
        LOGGER.warning("Validation: blocked disallowed DML/DDL")
        return final_result

    cleaned_sql = _cleanup_sql(sql_string, MAX_NUM_ROWS)
    LOGGER.debug("Validation: cleaned SQL:\n%s", cleaned_sql)

    try:
        query_job = get_bq_client().query(cleaned_sql)
        results = query_job.result()
        LOGGER.info("Validation: query executed successfully")

        rows = _format_bq_rows(results, MAX_NUM_ROWS) if results.schema else []
        tool_context.state["query_result"] = rows
        final_result["query_result"] = rows

        if not rows:
            final_result["error_message"] = "Valid SQL. Query executed successfully (no results)."
            LOGGER.info("Validation: valid SQL, zero rows.")
        else:
            LOGGER.info("Validation: valid SQL, %d row(s).", len(rows))

    except Exception as exc:  # noqa: BLE001
        final_result["error_message"] = f"Invalid SQL: {exc}"
        LOGGER.exception("Validation: query failed")

    LOGGER.debug("Validation: final_result=%s", final_result)
    return final_result


# ------------------------------------------------------------------------------
# Serialization helper for sample DDL inserts
# ------------------------------------------------------------------------------
def _serialize_value_for_sql(value):
    """Serializes a Python value from a pandas DataFrame into a BigQuery SQL literal."""
    if pd.isna(value):
        return "NULL"
    if isinstance(value, str):
        # Escape single quotes and backslashes for SQL strings.
        return f"'{value.replace('\\', '\\\\').replace("'", "''")}'"
    if isinstance(value, bytes):
        return f"b'{value.decode('utf-8', 'replace').replace('\\', '\\\\').replace("'", "''")}'"
    if isinstance(value, (datetime.datetime, datetime.date, pd.Timestamp)):
        # Timestamps and datetimes need to be quoted.
        return f"'{value}'"
    if isinstance(value, (list, np.ndarray)):
        # Format arrays.
        return f"[{', '.join(_serialize_value_for_sql(v) for v in value)}]"
    if isinstance(value, dict):
        # For STRUCT, BQ expects ('val1', 'val2', ...).
        # The values() order from the dataframe should match the column order.
        return f"({', '.join(_serialize_value_for_sql(v) for v in value.values())})"
    return str(value)