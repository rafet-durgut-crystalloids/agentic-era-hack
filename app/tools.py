"""
Top level tools for Promosphere
"""

from google.adk.tools import ToolContext
from google.adk.tools.agent_tool import AgentTool
import json
from typing import List
# from .sub_agents import data_analysis, db_agent
from .sub_agents import data_analysis_agent


async def call_data_analytics_agent(
    question: str,
    tool_context: ToolContext,
):
    """Tool to call data analysis agent."""
    print("\ncall_data_analytics_agent:")

    agent_tool = AgentTool(agent=data_analysis_agent)

    da_agent_output = await agent_tool.run_async(
        args={"request": question}, tool_context=tool_context
    )

    tool_context.state["da_agent_output"] = da_agent_output
    print("da agent output =", da_agent_output)
    return da_agent_output