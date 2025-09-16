"""This file contains the tools used by the database agent (BigQuery + NL2SQL)."""

from __future__ import annotations

import datetime
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from google.adk.tools import ToolContext
from google.cloud import bigquery
from google.genai import Client

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
# Constants / Config
# ------------------------------------------------------------------------------
MAX_NUM_ROWS: int = int(os.getenv("NL2SQL_MAX_ROWS", "80"))
DISALLOWED_DML_RE = re.compile(
    r"(?i)\b(update|delete|drop|insert|create|alter|truncate|merge)\b"
)

# ------------------------------------------------------------------------------
# Lazy singletons
# ------------------------------------------------------------------------------
_bq_client: Optional[bigquery.Client] = None
_llm_client: Optional[Client] = None

# ------------------------------------------------------------------------------
# Public globals kept for backward-compat (but filled via getters)
# ------------------------------------------------------------------------------
database_settings: Optional[Dict[str, Any]] = None


# ==============================================================================
# Clients
# ==============================================================================
def get_bq_client() -> bigquery.Client:
    """Get or create a BigQuery client (compute project)."""
    global _bq_client
    if _bq_client is None:
        compute_project = get_env_var("BQ_COMPUTE_PROJECT_ID")
        LOGGER.info("Creating BigQuery client (project=%s)", compute_project)
        _bq_client = bigquery.Client(project=compute_project)
    return _bq_client


def get_llm_client() -> Client:
    """Get or create a Google GenAI client (Vertex mode)."""
    global _llm_client
    if _llm_client is None:
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        LOGGER.info("Initializing GenAI client (vertexai=True, project=%s, location=%s)", project, location)
        _llm_client = Client(vertexai=True, project=project, location=location)
    return _llm_client


# ==============================================================================
# Database settings cache
# ==============================================================================
def get_database_settings() -> Dict[str, Any]:
    """Return cached DB settings; build if missing."""
    global database_settings
    if database_settings is None:
        database_settings = update_database_settings()
    return database_settings


def update_database_settings() -> Dict[str, Any]:
    """Rebuild DDL schema snapshot for the dataset."""
    LOGGER.info("Updating database settings (DDL snapshot)")
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
    return settings


# ==============================================================================
# Schema → DDL (with sample rows)
# ==============================================================================
def get_bigquery_schema(
    dataset_id: str,
    data_project_id: str,
    client: Optional[bigquery.Client] = None,
    compute_project_id: Optional[str] = None,
) -> str:
    """Retrieve schema and generate DDL (plus sample inserts) for a dataset."""
    if client is None:
        LOGGER.info("No BQ client provided; creating with compute project")
        client = bigquery.Client(project=compute_project_id)

    dataset_ref = bigquery.DatasetReference(data_project_id, dataset_id)
    ddl_chunks: List[str] = []

    info_schema_query = (
        "SELECT table_name "
        f"FROM `{data_project_id}.{dataset_id}.INFORMATION_SCHEMA.TABLES`"
    )
    LOGGER.debug("Schema discovery query: %s", info_schema_query)

    for row in client.query(info_schema_query).result():
        table_ref = dataset_ref.table(row.table_name)
        table_obj = client.get_table(table_ref)
        LOGGER.info("Discovered %s: %s", table_obj.table_type, table_ref.path)

        if table_obj.table_type == "VIEW":
            view_query = table_obj.view_query or ""
            ddl_chunks.append(
                "CREATE OR REPLACE VIEW `{}` AS\n{};\n\n".format(table_ref, view_query)
            )
            continue

        if table_obj.table_type == "EXTERNAL":
            _append_external_iceberg_ddl_if_applicable(ddl_chunks, table_obj)
            continue

        if table_obj.table_type == "TABLE":
            ddl_chunks.append(_ddl_for_table_with_samples(client, table_obj))
            continue

        # Skip other types (MATERIALIZED_VIEW, SNAPSHOT, etc.)

    return "".join(ddl_chunks)


def _append_external_iceberg_ddl_if_applicable(
    ddl_chunks: List[str], table_obj: bigquery.Table
) -> None:
    cfg = table_obj.external_data_configuration
    if not (cfg and cfg.source_format == "ICEBERG"):
        return

    uris_list_str = ",\n    ".join("'{}'".format(uri) for uri in cfg.source_uris)
    col_defs: List[str] = []
    for field in table_obj.schema:
        col_type = "ARRAY<{}>".format(field.field_type) if field.mode == "REPEATED" else field.field_type
        col_defs.append("  `{}` {}".format(field.name, col_type))
    columns_str = ",\n".join(col_defs)

    ddl_chunks.append(
        (
            "CREATE EXTERNAL TABLE `{}` (\n{}\n)\n"
            "WITH CONNECTION `{}`\n"
            "OPTIONS (\n"
            "  uris = [{}],\n"
            "  format = 'ICEBERG'\n"
            ");\n\n"
        ).format(table_obj.reference, columns_str, cfg.connection_id, uris_list_str)
    )


def _ddl_for_table_with_samples(client: bigquery.Client, table_obj: bigquery.Table) -> str:
    # Column definitions with descriptions (avoid backslashes in f-expressions)
    cols: List[str] = []
    for field in table_obj.schema:
        col_type = "ARRAY<{}>".format(field.field_type) if field.mode == "REPEATED" else field.field_type
        col_def = "  `{}` {}".format(field.name, col_type)
        if field.description:
            safe_desc = str(field.description).replace("'", "''")
            col_def += " OPTIONS(description='{}')".format(safe_desc)
        cols.append(col_def)

    cols_joined = ",\n".join(cols)
    ddl = "CREATE OR REPLACE TABLE `{}` (\n{}\n);\n\n".format(table_obj.reference, cols_joined)

    # Sample rows (best-effort)
    try:
        sample_query = "SELECT * FROM `{}` LIMIT 5".format(table_obj.reference)
        LOGGER.debug("Sampling query: %s", sample_query)
        df = client.query(sample_query).to_dataframe()
        if not df.empty:
            ddl += "-- Example values for table `{}`:\n".format(table_obj.reference)
            for _, r in df.iterrows():
                values_str = ", ".join(_serialize_value_for_sql(v) for v in r.values)
                ddl += "INSERT INTO `{}` VALUES ({});\n".format(table_obj.reference, values_str)
        ddl += "\n"
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Sample retrieval failed for %s: %s", table_obj.reference.path, exc)
        ddl += "-- NOTE: Could not retrieve sample rows for table {}.\n\n".format(table_obj.reference.path)

    return ddl


# ==============================================================================
# NL2SQL generation
# ==============================================================================
def initial_bq_nl2sql(question: str, tool_context: ToolContext) -> str:
    """Generate an initial SQL query from a natural language question."""
    LOGGER.info("NL2SQL: building prompt for question")
    ddl_schema = tool_context.state["database_settings"]["bq_ddl_schema"]

    prompt_template = (
        "You are a BigQuery SQL expert. Given the schema and a natural-language question, "
        "produce a valid GoogleSQL query that answers the request.\n\n"
        "Rules:\n"
        "- Use fully-qualified table names with backticks: `project.dataset.table`.\n"
        "- Minimize joins; ensure join column types match.\n"
        "- Every non-aggregated SELECT column must appear in GROUP BY.\n"
        "- Use valid GoogleSQL; alias with AS; wrap subqueries/UNIONs in parentheses.\n"
        "- Only use columns present in the provided schema under their correct tables.\n"
        "- Apply sensible WHERE/HAVING filters.\n"
        "- Cap results to < {max_rows} rows (add LIMIT if needed).\n\n"
        "Schema (tables with samples):\n{schema}\n\n"
        "User question:\n{question}\n\n"
        "Return only the SQL."
    )

    prompt = prompt_template.format(
        max_rows=MAX_NUM_ROWS, schema=ddl_schema, question=question
    )

    model_name = (
        os.getenv("BASELINE_NL2SQL_MODEL")
        or os.getenv("GENERIC_MODEL")
        or "gemini-1.5-flash-002"
    )

    LOGGER.info("NL2SQL: generating with model=%s", model_name)
    t0 = time.time()
    resp = get_llm_client().models.generate_content(
        model=model_name,
        contents=prompt,
        config={"temperature": 0.1},
    )
    elapsed_ms = (time.time() - t0) * 1000.0
    LOGGER.info("NL2SQL generation completed in %.1f ms", elapsed_ms)

    sql = (resp.text or "").strip()
    sql = sql.replace("```sql", "").replace("```", "").strip()
    LOGGER.debug("NL2SQL draft (first 200 chars): %s", sql[:200])

    tool_context.state["sql_query"] = sql
    return sql


# ==============================================================================
# Validation
# ==============================================================================
def run_bigquery_validation(sql_string: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Validate a BigQuery query by executing it (read-only) and summarizing the outcome.

    Returns:
      {
        "query_result": List[Dict] | None,
        "error_message": str | None
      }
    """
    LOGGER.info("Validation: starting")
    LOGGER.debug("Validation: original SQL:\n%s", sql_string)

    def cleanup_sql(raw: str) -> str:
        """Normalize escapes/newlines and ensure a LIMIT exists."""
        s = raw.replace('\\"', '"')
        s = s.replace("\\\n", "\n")
        s = s.replace("\\'", "'")
        s = s.replace("\\n", "\n").strip()
        if "limit" not in s.lower():
            s = s + " limit " + str(MAX_NUM_ROWS)
        return s

    final_result: Dict[str, Any] = {"query_result": None, "error_message": None}

    # Block DML/DDL to enforce read-only validation
    if DISALLOWED_DML_RE.search(sql_string or ""):
        msg = "Invalid SQL: Contains disallowed DML/DDL operations."
        final_result["error_message"] = msg
        LOGGER.warning(msg)
        return final_result

    cleaned_sql = cleanup_sql(sql_string or "")
    LOGGER.debug("Validation: cleaned SQL:\n%s", cleaned_sql)

    try:
        results = get_bq_client().query(cleaned_sql).result()
        LOGGER.info("Validation: query executed")

        rows = _format_bq_rows(results, MAX_NUM_ROWS) if results.schema else []
        tool_context.state["query_result"] = rows
        final_result["query_result"] = rows

        if not rows:
            final_result["error_message"] = "Valid SQL. Query executed successfully (no results)."
            LOGGER.info("Validation: zero rows")
        else:
            final_result["error_message"] = None  # explicit success
            LOGGER.info("Validation: %d row(s) returned", len(rows))

    except Exception as exc:  # noqa: BLE001
        final_result["error_message"] = f"Invalid SQL: {exc}"
        LOGGER.exception("Validation: query failed")

    LOGGER.debug("Validation: final_result=%s", final_result)
    return final_result


def _format_bq_rows(results: bigquery.table.RowIterator, max_rows: int) -> List[Dict[str, Any]]:
    """Convert BQ results to JSON-serializable rows (date-friendly)."""
    out: List[Dict[str, Any]] = []
    for row in results:
        converted: Dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, datetime.date):
                converted[key] = value.strftime("%Y-%m-%d")
            else:
                converted[key] = value
        out.append(converted)
        if len(out) >= max_rows:
            break
    return out


# ==============================================================================
# Serialization helper for sample DDL inserts
# ==============================================================================
def _serialize_value_for_sql(value: Any) -> str:
    """Serialize a Python value from pandas into a BigQuery SQL literal."""
    if pd.isna(value):
        return "NULL"
    if isinstance(value, str):
        # Escape backslashes and single quotes
        s = value.replace("\\", "\\\\").replace("'", "''")
        return "'" + s + "'"
    if isinstance(value, bytes):
        s = value.decode("utf-8", "replace").replace("\\", "\\\\").replace("'", "''")
        return "b'" + s + "'"
    if isinstance(value, (datetime.datetime, datetime.date, pd.Timestamp)):
        return "'" + str(value) + "'"
    if isinstance(value, (list, np.ndarray)):
        inner = ", ".join(_serialize_value_for_sql(v) for v in value)
        return "[" + inner + "]"
    if isinstance(value, dict):
        inner = ", ".join(_serialize_value_for_sql(v) for v in value.values())
        return "(" + inner + ")"
    return str(value)