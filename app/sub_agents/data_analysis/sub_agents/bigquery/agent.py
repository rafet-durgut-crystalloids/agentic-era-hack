"""Database Agent: get data from database (BigQuery) using NL2SQL."""

import os

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.genai import types

from . import tools
from .prompts import return_instructions_bigquery


def setup_before_agent_call(callback_context: CallbackContext) -> None:
    """Setup the agent."""

    if "database_settings" not in callback_context.state:
        callback_context.state["database_settings"] = \
            tools.get_database_settings()


database_query_agent = Agent(
    model=os.getenv("GENERIC_MODEL"),
    name="database_query_agent",
    instruction=return_instructions_bigquery(),
    tools=[
        tools.initial_bq_nl2sql,
        tools.run_bigquery_validation,
    ],
    before_agent_callback=setup_before_agent_call,
    generate_content_config=types.GenerateContentConfig(temperature=0.01),
)
