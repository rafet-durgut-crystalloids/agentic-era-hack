import subprocess
from typing import Any, Dict, Optional

from google.adk.tools import FunctionTool
from .utils import run_cli, run_gcloud
from ..search.agent import search_agent
from google.adk.tools import ToolContext
from google.adk.tools.agent_tool import AgentTool


def cli_run(
    cmd: str,
    check: bool = True,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Execute an arbitrary shell command.

    Use this tool for general shell commands (non-GCP or GCP).
    Pass the entire command as a single string, e.g. "ls -la /tmp".

    Args:
      cmd: Full command string (e.g., "ls -la" or "bash script.sh").
      check: If True, non-zero exit raises error (returned as status="error").
      cwd: Optional working directory.
      env: Optional environment variable overrides.

    Returns:
      {
        "status": "success" | "error",
        "return_code": int,
        "stdout": str,
        "stderr": str
      }
    """
    try:
        ret, out, err = run_cli(cmd, check=check, cwd=cwd, env=env)
        return {"status": "success", "return_code": ret, "stdout": out, "stderr": err}
    except subprocess.CalledProcessError as e:
        return {
            "status": "error",
            "return_code": e.returncode,
            "stdout": e.output or "",
            "stderr": e.stderr or "",
        }


cli_run_tool = FunctionTool(func=cli_run)


def cli_gcloud(
    args: str,
    check: bool = True,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Execute a gcloud CLI command.

    Use this tool for Google Cloud commands. Pass only the arguments
    (without the leading 'gcloud') as a single string, e.g.:
      "firestore databases create --location=eur3 --project=my-proj"

    Args:
      args: Arguments for gcloud as a single string.
      check: If True, non-zero exit raises error (returned as status="error").
      cwd: Optional working directory.
      env: Optional environment variable overrides.

    Returns:
      {
        "status": "success" | "error",
        "return_code": int,
        "stdout": str,
        "stderr": str
      }
    """
    try:
        ret, out, err = run_gcloud(args, check=check, cwd=cwd, env=env)
        return {"status": "success", "return_code": ret, "stdout": out, "stderr": err}
    except subprocess.CalledProcessError as e:
        return {
            "status": "error",
            "return_code": e.returncode,
            "stdout": e.output or "",
            "stderr": e.stderr or "",
        }

async def call_search_agent(
    request: str,
    tool_context: ToolContext,
):
    """
    Tool to call the Search Agent.
    Args:
    request: A clear natural-language query describing the information needed.
    Examples:
                 - "Find the correct usage of gcloud compute zones"
                 - "Find the correct usage of cloud scheduler jobs create"
                 - "Find gcloud cli cloud function parameters."
    """
    print("\ncall_search_agent with request:", request)
    agent_tool = AgentTool(agent=search_agent)
    search_agent_output = await agent_tool.run_async(
        args={"request": request}, tool_context=tool_context
    )
    tool_context.state["search_agent_output"] = search_agent_output
    print("search_agent_output =", search_agent_output)
    return search_agent_output


cli_gcloud_tool = FunctionTool(func=cli_gcloud)


ALL_CLI_TOOLS = [cli_run_tool, cli_gcloud_tool]