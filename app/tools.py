"""
Top level tools for Promosphere
"""

from google.adk.tools import ToolContext
from google.adk.tools.agent_tool import AgentTool
import json
from typing import List
# from .sub_agents import data_analysis, db_agent
from .sub_agents import data_analysis_agent, resource_agent, search_agent


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


async def call_resource_agent(
    request: str,
    tool_context: ToolContext,
):
    """
    Tool to call the Google Cloud Resource Agent.

    Args:
      request: A natural language instruction describing the resource management
               task to perform. For example:
                 - "Create a Firestore Native database in location eur3 for project my-project"
                 - "Fetch document 'user_123' from 'users' collection"
                 - "Update field 'status' to 'active' in document 'user_123' in collection 'users'"
    """
    print("\ncall_resource_agent with request:", request)
    agent_tool = AgentTool(agent=resource_agent)
    resource_agent_output = await agent_tool.run_async(
        args={"request": request}, tool_context=tool_context
    )
    tool_context.state["resource_agent_output"] = resource_agent_output
    print("resource_agent_output =", resource_agent_output)
    return resource_agent_output   

async def call_search_agent(
    request: str,
    tool_context: ToolContext,
):
    """
    Tool to call the Search Agent.
    Args:
    request: A clear natural-language query describing the information needed.
    Examples:
                 - "Find the most recent benchmarks for e-commerce loyalty programs."
                 - "What are current EU SMS marketing regulations in 2025?"
                 - "Summarize competitor loyalty strategies."
    """
    print("\ncall_search_agent with request:", request)
    agent_tool = AgentTool(agent=search_agent)
    search_agent_output = await agent_tool.run_async(
        args={"request": request}, tool_context=tool_context
    )
    tool_context.state["search_agent_output"] = search_agent_output
    print("search_agent_output =", search_agent_output)
    return search_agent_output