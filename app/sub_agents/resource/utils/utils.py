import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


from ....sub_agents.storage.utils import download_json as gcs_download_json
from ....sub_agents.storage.utils import upload_json as gcs_upload_json

# Config from env
RESOURCE_REGISTRY_BUCKET = os.getenv("RESOURCE_REGISTRY_BUCKET")
RESOURCE_REGISTRY_FILE = os.getenv("RESOURCE_REGISTRY_FILE", "resource_registry.json")

# Optional context helpers (used to pre-fill registry base)
RESOURCES_PROJECT = os.getenv("RESOURCES_PROJECT", "")
RESOURCES_LOCATION = os.getenv("RESOURCES_LOCATION", "")
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")

if not RESOURCE_REGISTRY_BUCKET:
    raise RuntimeError("RESOURCE_REGISTRY_BUCKET env var must be set.")


# Internal helpers
def _now_iso() -> str:
    # Match examples like 2025-08-10T12:00:00Z
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _empty_registry() -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "project_id": RESOURCES_PROJECT,
        "default_location": RESOURCES_LOCATION,
        "environment": ENVIRONMENT,
        "resources": [],
    }


def _load_registry() -> Dict[str, Any]:
    """Load the registry JSON from GCS. If missing or invalid, start a new one."""
    try:
        data = gcs_download_json(RESOURCE_REGISTRY_BUCKET, RESOURCE_REGISTRY_FILE)
        # Basic shape enforcement
        if not isinstance(data, dict) or "resources" not in data or not isinstance(data["resources"], list):
            return _empty_registry()
        return data
    except Exception:
        # If blob doesn't exist or any other error → initialize minimal structure
        return _empty_registry()


def _save_registry(registry: Dict[str, Any]) -> None:
    gcs_upload_json(RESOURCE_REGISTRY_BUCKET, RESOURCE_REGISTRY_FILE, registry)


def _find_resource_index(registry: Dict[str, Any], resource_id: str) -> Optional[int]:
    for i, r in enumerate(registry.get("resources", [])):
        if r.get("id") == resource_id:
            return i
    return None


def _validate_resource_payload(resource: Dict[str, Any]) -> None:
    """
    Minimal schema validation. Raises ValueError if critical fields are missing.
    """
    required = ["id", "type", "name"]
    for k in required:
        if not resource.get(k):
            raise ValueError(f"Missing required resource field: '{k}'")
    # Defaults
    resource.setdefault("location", RESOURCES_LOCATION or "")
    resource.setdefault("unique", False)
    resource.setdefault("purpose", "")
    resource.setdefault("config", {})
    resource.setdefault("outputs", {})
    resource.setdefault("depends_on", [])
    resource.setdefault("tags", {})


# Public API
def add_resource(resource: Dict[str, Any]) -> str:
    """
    Add a resource to the registry.

    Args:
        resource: dict with keys:
          - id (str) REQUIRED and must be globally unique within the registry
          - type (str) e.g., "firestore_db", "cloud_function", "storage_bucket"
          - name (str)
          - location (str, optional; defaults from env)
          - unique (bool, optional)
          - purpose (str, optional)
          - config (dict, optional; e.g., {"delete_protection": true})
          - outputs (dict, optional)
          - depends_on (list[str], optional)
          - tags (dict, optional)

    Returns:
        The resource id.

    Raises:
        ValueError if id already exists or payload invalid.
    """
    _validate_resource_payload(resource)
    registry = _load_registry()

    if _find_resource_index(registry, resource["id"]) is not None:
        raise ValueError(f"Resource with id '{resource['id']}' already exists.")

    now = _now_iso()
    resource.setdefault("created_at", now)
    resource["updated_at"] = now

    registry["resources"].append(resource)
    _save_registry(registry)
    return resource["id"]


def delete_resource(resource_id: str) -> bool:
    """
    Delete a resource by id. Will refuse to delete if delete_protection=true.

    Args:
        resource_id: id string of the resource (e.g., "firestore_db/(default)")

    Returns:
        True if deleted, False if not found.

    Raises:
        PermissionError if delete_protection is True.
    """
    registry = _load_registry()
    idx = _find_resource_index(registry, resource_id)
    if idx is None:
        return False

    res = registry["resources"][idx]
    delete_protection = bool(res.get("config", {}).get("delete_protection", False))
    if delete_protection:
        raise PermissionError(f"Resource '{resource_id}' has delete_protection enabled.")

    # Remove and save
    registry["resources"].pop(idx)
    _save_registry(registry)
    return True


def update_resource(resource_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update fields of an existing resource (merge/replace by keys).

    Args:
        resource_id: id of the resource to update
        updates: partial dict to merge. 'id' cannot be changed.

    Returns:
        The updated resource dict.

    Raises:
        ValueError if resource not found or if 'id' in updates != resource_id.
    """
    if "id" in updates and updates["id"] != resource_id:
        raise ValueError("Cannot change resource 'id' in update.")

    registry = _load_registry()
    idx = _find_resource_index(registry, resource_id)
    if idx is None:
        raise ValueError(f"Resource with id '{resource_id}' not found.")

    current = registry["resources"][idx]

    # Shallow merge for top-level keys; nested objects like config/outputs/tags are overwritten
    merged = {**current, **updates, "updated_at": _now_iso()}

    # Keep created_at from original if missing
    if "created_at" not in merged and "created_at" in current:
        merged["created_at"] = current["created_at"]

    # Validate minimal fields after merge
    _validate_resource_payload(merged)

    registry["resources"][idx] = merged
    _save_registry(registry)
    return merged


def list_resources(resource_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List resources, optionally filtered by type.

    Args:
        resource_type: e.g., "firestore_db", "cloud_function", "storage_bucket"

    Returns:
        List of resource dicts.
    """
    registry = _load_registry()
    items = registry.get("resources", [])
    if resource_type:
        return [r for r in items if r.get("type") == resource_type]
    return items


def get_resources_json(pretty: bool = True) -> str:
    """
    Return the entire registry JSON as a string.

    Args:
        pretty: whether to pretty-print.

    Returns:
        JSON string of the registry.
    """
    registry = _load_registry()
    return json.dumps(registry, indent=2 if pretty else None)