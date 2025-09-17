from typing import Dict, Any, List, Optional

from google.adk.tools import FunctionTool, ToolContext

from .utils import (
    get_business_config_file as _fetch_business_config,
    get_strategies_file as _fetch_strategies,
    create_strategy as _create_strategy,
    update_strategy_by_id as _update_strategy,
    delete_strategy_by_id as _delete_strategy,
    create_strategy_file as _create_strategy_file,
    create_business_config_file as _create_business_config_file,
)


def get_business_configuration() -> Dict[str, Any]:
    """Retrieves the business configuration (definition, description, goals).

    Use this tool when the agent needs to know the business context.

    Returns:
      - status: "success" or "error"
      - config: the business_config dict (on success)
      - error_message: the exception text (on error)
    """
    try:
        config = _fetch_business_config()
        return {"status": "success", "config": config}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}


get_business_configuration_tool = FunctionTool(get_business_configuration)


def get_all_strategies() -> Dict[str, Any]:
    """Fetches the list of all active strategies.

    Returns:
      - status: "success" or "error"
      - strategies: list of strategy dicts (on success)
      - error_message: the exception text (on error)
    """
    try:
        strategies = _fetch_strategies()
        return {"status": "success", "strategies": strategies}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}


get_all_strategies_tool = FunctionTool(get_all_strategies)


def create_strategy(strategy: Dict[str, Any]) -> Dict[str, Any]:
    """Adds a new strategy to the strategies configuration.

    Args:
      strategy: dict with keys:
        - strategy_name (str)
        - strategy_purpose (str)
        - strategy_definition (str)
        - strategy_creation_date (str, YYYY-MM-DD)

    Returns:
      - status: "success" or "error"
      - strategy_id: the new UUID (on success)
      - error_message: exception text (on error)
    """
    try:
        new_id = _create_strategy(strategy)
        return {"status": "success", "strategy_id": new_id}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}


create_strategy_tool = FunctionTool(create_strategy)


def update_strategy(updated_strategy: Dict[str, Any]) -> Dict[str, Any]:
    """Updates an existing strategy by its ID.

    Args:
      updated_strategy: dict containing at least:
        - strategy_id (str)
      plus any fields to update.

    Returns:
      - status: "success" or "error"
      - error_message: if strategy not found or on exception
    """
    try:
        ok = _update_strategy(updated_strategy)
        if not ok:
            return {"status": "error", "error_message": "Strategy not found"}
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}


update_strategy_tool = FunctionTool(update_strategy)


def delete_strategy(strategy_id: str) -> Dict[str, Any]:
    """Deletes a strategy by its ID.

    Args:
      strategy_id: The UUID of the strategy to delete.

    Returns:
      - status: "success" or "error"
      - error_message: if strategy not found or on exception
    """
    try:
        ok = _delete_strategy(strategy_id)
        if not ok:
            return {"status": "error", "error_message": "Strategy not found"}
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}


delete_strategy_tool = FunctionTool(delete_strategy)


def create_strategy_file_tool_fn(filename: Optional[str] = "strategies.json") -> Dict[str, Any]:
    """Creates an empty strategies file (JSON array) in Cloud Storage.

    Args:
      filename: Optional override for the object name. Defaults to 'strategies.json'.

    Returns:
      - status: "success" or "error"
      - gcs_uri: the URI of the created file (on success)
      - error_message: exception text (on error)
    """
    try:
        uri = _create_strategy_file(filename or "strategies.json")
        return {"status": "success", "gcs_uri": uri}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}


create_strategy_file_tool = FunctionTool(create_strategy_file_tool_fn)


def create_business_config_file_tool_fn(
    config: Dict[str, Any],
    filename: Optional[str] = "business_config.json",
) -> Dict[str, Any]:
    """Creates a business configuration file in Cloud Storage.

    Args:
      config: Dict with at least 'name'. Other fields will be defaulted if missing.
      filename: Optional override; defaults to 'business_config.json'.

    Returns:
      - status: "success" or "error"
      - gcs_uri: the URI of the created file (on success)
      - error_message: exception text (on error)
    """
    try:
        uri = _create_business_config_file(config, filename or "business_config.json")
        return {"status": "success", "gcs_uri": uri}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}


create_business_config_file_tool = FunctionTool(create_business_config_file_tool_fn)


ALL_STORAGE_TOOLS = [
    get_business_configuration_tool,
    get_all_strategies_tool,
    create_strategy_tool,
    update_strategy_tool,
    delete_strategy_tool,
    create_strategy_file_tool,
    create_business_config_file_tool,
]