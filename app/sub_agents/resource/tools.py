from typing import Any, Dict, Optional, List
import json

from google.adk.tools import FunctionTool, ToolContext
from google.adk.tools.agent_tool import AgentTool
from .. import cli_agent

from .utils.firestore.dao import (
    create_document as _create_document,
    get_document as _get_document,
    update_document as _update_document,
    delete_document as _delete_document,
    update_document_field as _update_document_field,
    get_all_documents as _get_all_documents
)

def fs_create_document(
    collection: str,
    document: Dict[str, Any],
    document_id: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        new_id = _create_document(collection=collection, document=document, document_id=document_id)
        return {"status": "success", "document_id": new_id}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

fs_create_document_tool = FunctionTool(func=fs_create_document)

def fs_get_document(
    collection: str,
    document_id: str,
) -> Dict[str, Any]:
    try:
        doc = _get_document(collection=collection, document_id=document_id)
        return {
            "status": "success",
            "found": doc is not None,
            "document": doc if doc is not None else None,
        }
    except Exception as e:
        return {"status": "error", "found": False, "document": None, "error_message": str(e)}

fs_get_document_tool = FunctionTool(func=fs_get_document)

def fs_get_all_documents(
    collection: str,
    include_ids: bool = True,
) -> Dict[str, Any]:
    """
    Retrieve all documents in a collection.

    Args:
      collection: Firestore collection name.
      include_ids: If True, include each document's ID under key 'id'.
    """
    try:
        docs = _get_all_documents(collection=collection, include_ids=include_ids)
        return {"status": "success", "documents": docs}
    except Exception as e:
        return {"status": "error", "documents": [], "error_message": str(e)}

fs_get_all_documents_tool = FunctionTool(func=fs_get_all_documents)

def fs_update_document(
    collection: str,
    document_id: str,
    new_document: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        _update_document(collection=collection, document_id=document_id, new_document=new_document)
        return {"status": "success", "document_id": document_id}
    except Exception as e:
        return {"status": "error", "document_id": document_id, "error_message": str(e)}

fs_update_document_tool = FunctionTool(func=fs_update_document)

def fs_update_document_field(
    collection: str,
    document_id: str,
    field_name: str,
    new_value: str,
) -> Dict[str, Any]:
    """
    Updates a single field on a Firestore document.

    new_value must be JSON-encoded (e.g., "42", "true", "\"Amsterdam\"", "{\"nested\":1}").
    If parsing fails, the raw string is used.
    """
    try:
        try:
            parsed_value = json.loads(new_value)
        except Exception:
            parsed_value = new_value

        _update_document_field(
            collection=collection,
            document_id=document_id,
            field_name=field_name,
            new_value=parsed_value,
        )
        return {
            "status": "success",
            "document_id": document_id,
            "updated_field": field_name,
        }
    except Exception as e:
        return {
            "status": "error",
            "document_id": document_id,
            "updated_field": field_name,
            "error_message": str(e),
        }

fs_update_document_field_tool = FunctionTool(func=fs_update_document_field)

def fs_delete_document(
    collection: str,
    document_id: str,
) -> Dict[str, Any]:
    try:
        _delete_document(collection=collection, document_id=document_id)
        return {"status": "success", "document_id": document_id}
    except Exception as e:
        return {"status": "error", "document_id": document_id, "error_message": str(e)}

fs_delete_document_tool = FunctionTool(func=fs_delete_document)

async def call_cli_agent(
    request: str,
    tool_context: ToolContext,
):
    """
    Tool to call the CLI automation agent.

    Args:
      request: Natural-language instruction describing the CLI task.

    Returns:
      The CLI agent's response (string). Also stored in state under "cli_agent_output".
    """
    print("\ncall_cli_agent with request:", request)
    agent_tool = AgentTool(agent=cli_agent)
    cli_agent_output = await agent_tool.run_async(
        args={"request": request}, tool_context=tool_context
    )
    tool_context.state["cli_agent_output"] = cli_agent_output
    print("cli_agent_output =", cli_agent_output)
    return cli_agent_output

ALL_RESOURCE_TOOLS: List[Any] = [
    fs_create_document_tool,
    fs_get_document_tool,
    fs_get_all_documents_tool,
    fs_update_document_tool,
    fs_update_document_field_tool,
    fs_delete_document_tool,
    call_cli_agent,
]


async def call_resource_registry_agent():
    return None