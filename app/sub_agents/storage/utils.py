import os
import json
import uuid
from typing import Optional, Dict, Any, List

from google.cloud import storage

# env configs
BUSINESS_CONFIG_PROJECT = os.getenv("BUSINESS_CONFIG_JSON_PROJECT")
BUSINESS_CONFIG_BUCKET = os.getenv("BUSINESS_CONFIIG_JSON_BUCKET")
BUSINESS_CONFIG_FILE = os.getenv("BUSINESS_CONFIIG_JSON_FILE")

STRATEGIES_PROJECT = os.getenv("STRATEGIES_JSON_PROJECT")
STRATEGIES_BUCKET = os.getenv("STRATEGIES_JSON_BUCKET")
STRATEGIES_FILE = os.getenv("STRATEGIES_JSON_FILE")


def _get_storage_client() -> storage.Client:
    """Initialize and return a Google Cloud Storage client."""
    return storage.Client()


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


# Example usage:
# config = get_business_config_file()
# strategies = get_strategies_file()
# success = delete_strategy_by_id("some-uuid")
# updated = update_strategy_by_id({"strategy_id": "some-uuid", "strategy_name": "new_name"})
# new_id = create_strategy({
#     "strategy_name": "weekend_bonus",
#     "strategy_purpose": "Drive weekend sales",
#     "strategy_definition": "Send 10% off coupon every Friday evening to weekend_shopper group.",
#     "strategy_creation_date": "2025-07-28"
# })

