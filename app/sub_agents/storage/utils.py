import os
import json
import uuid
from typing import Optional, Dict, Any, List

from google.cloud import storage
from google.api_core.exceptions import NotFound, Conflict

# env configs
BUSINESS_CONFIG_PROJECT = os.getenv("BUSINESS_CONFIG_JSON_PROJECT")
BUSINESS_CONFIG_BUCKET = os.getenv("BUSINESS_CONFIIG_JSON_BUCKET")
BUSINESS_CONFIG_FILE = os.getenv("BUSINESS_CONFIIG_JSON_FILE")

STRATEGIES_PROJECT = os.getenv("STRATEGIES_JSON_PROJECT")
STRATEGIES_BUCKET = os.getenv("STRATEGIES_JSON_BUCKET")
STRATEGIES_FILE = os.getenv("STRATEGIES_JSON_FILE")


def _get_storage_client(project: Optional[str] = None) -> storage.Client:
    """Initialize and return a Google Cloud Storage client (optionally for a project)."""
    return storage.Client(project=project) if project else storage.Client()


def _get_bucket(project: Optional[str], bucket_name: str) -> storage.Bucket:
    """Helper to fetch a bucket with an optional explicit project."""
    client = _get_storage_client(project)
    return client.bucket(bucket_name)


def _blob_exists(project: Optional[str], bucket_name: str, blob_name: str) -> bool:
    """Check if a blob exists in GCS (optionally under a specific project)."""
    client = _get_storage_client(project)
    blob = client.bucket(bucket_name).blob(blob_name)
    return blob.exists(client)


def _ensure_bucket_exists(project: Optional[str], bucket_name: str) -> storage.Bucket:
    """
    Ensure a GCS bucket exists. If not, create it.
    Args:
        project: optional GCP project to bind bucket to
        bucket_name: name of the bucket
    Returns:
        The bucket object.
    """
    client = _get_storage_client(project)
    try:
        bucket = client.get_bucket(bucket_name)
    except NotFound:
        # Create bucket if not found
        try:
            bucket = client.create_bucket(bucket_name)
        except Conflict:
            bucket = client.get_bucket(bucket_name)
    return bucket


def download_json(bucket_name: str, blob_name: str) -> Any:
    """Download a JSON blob from GCS and parse it."""
    client = _get_storage_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    content = blob.download_as_text()
    return json.loads(content)


def upload_json(bucket_name: str, blob_name: str, data: Any) -> None:
    """Upload a JSON-serializable object to GCS."""
    client = _get_storage_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(json.dumps(data, indent=2), content_type="application/json")


def get_business_config_file(location: Optional[str] = None) -> Dict[str, Any]:
    """
    Get the business config JSON from Cloud Storage.

    Args:
        location: optional override for the filename in the bucket.

    Returns:
        Parsed JSON as a dict.
    """
    file_name = location or BUSINESS_CONFIG_FILE
    return download_json(BUSINESS_CONFIG_BUCKET, file_name)


def get_strategies_file(file_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get the strategies JSON array from Cloud Storage.

    Args:
        file_name: optional override for the filename in the bucket.

    Returns:
        List of strategy dicts.
    """
    fname = file_name or STRATEGIES_FILE
    return download_json(STRATEGIES_BUCKET, fname)


def _save_strategies(strategies: List[Dict[str, Any]], file_name: Optional[str] = None) -> None:
    """Helper to save the strategies list back to Cloud Storage."""
    fname = file_name or STRATEGIES_FILE
    upload_json(STRATEGIES_BUCKET, fname, strategies)


def delete_strategy_by_id(strategy_id: str) -> bool:
    """
    Delete a single strategy by its ID.

    Args:
        strategy_id: the UUID of the strategy to remove.

    Returns:
        True if a strategy was deleted, False otherwise.
    """
    strategies = get_strategies_file()
    filtered = [s for s in strategies if s.get("strategy_id") != strategy_id]
    if len(filtered) == len(strategies):
        return False  # no strategy found
    _save_strategies(filtered)
    return True


def update_strategy_by_id(updated_strategy: Dict[str, Any]) -> bool:
    """
    Update an existing strategy object in the strategies JSON.

    Args:
        updated_strategy: dict containing at least 'strategy_id' and fields to update.

    Returns:
        True if updated, False if strategy not found.
    """
    if "strategy_id" not in updated_strategy:
        raise ValueError("updated_strategy must contain 'strategy_id'")

    strategies = get_strategies_file()
    updated = False
    for idx, strat in enumerate(strategies):
        if strat.get("strategy_id") == updated_strategy["strategy_id"]:
            strategies[idx] = {**strat, **updated_strategy}
            updated = True
            break

    if not updated:
        return False

    _save_strategies(strategies)
    return True


def create_strategy(strategy_json: Dict[str, Any]) -> str:
    """
    Add a new strategy object to the strategies JSON.

    Args:
        strategy_json: new strategy data (without 'strategy_id').

    Returns:
        The generated UUID for the new strategy.
    """
    strategies = get_strategies_file()
    new_id = strategy_json.get("strategy_id") or str(uuid.uuid4())
    strategy_json["strategy_id"] = new_id
    strategies.append(strategy_json)
    _save_strategies(strategies)
    return new_id


def create_strategy_file(filename: str = "strategies.json") -> str:
    if not STRATEGIES_BUCKET:
        raise EnvironmentError("STRATEGIES_JSON_BUCKET is not set")

    if _blob_exists(STRATEGIES_PROJECT, STRATEGIES_BUCKET, filename):
        raise FileExistsError(f"file already exists: gs://{STRATEGIES_BUCKET}/{filename}")

    bucket = _ensure_bucket_exists(STRATEGIES_PROJECT, STRATEGIES_BUCKET)
    blob = bucket.blob(filename)
    blob.upload_from_string("[]", content_type="application/json")

    return f"gs://{STRATEGIES_BUCKET}/{filename}"


def create_business_config_file(config: Dict[str, Any], filename: str = "business_config.json") -> str:
    if not BUSINESS_CONFIG_BUCKET:
        raise EnvironmentError("BUSINESS_CONFIIG_JSON_BUCKET is not set")

    name = (config.get("name") or "").strip() if isinstance(config.get("name"), str) else None
    if not name:
        raise ValueError("config must include a non-empty 'name' field")

    if _blob_exists(BUSINESS_CONFIG_PROJECT, BUSINESS_CONFIG_BUCKET, filename):
        raise FileExistsError(f"file already exists: gs://{BUSINESS_CONFIG_BUCKET}/{filename}")

    payload = {
        "name": name,
        "business_description": config.get("business_description", ""),
        "budget": config.get("budget", 0),
        "enable_budget_alerts": bool(config.get("enable_budget_alerts", False)),
        "allowed_campaign_channels": config.get("allowed_campaign_channels", []),
    }

    bucket = _ensure_bucket_exists(BUSINESS_CONFIG_PROJECT, BUSINESS_CONFIG_BUCKET)
    blob = bucket.blob(filename)
    blob.upload_from_string(json.dumps(payload, indent=2), content_type="application/json")

    return f"gs://{BUSINESS_CONFIG_BUCKET}/{filename}"