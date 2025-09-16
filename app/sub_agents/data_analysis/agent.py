"""Data analysis agent.
Get data (natural language to sql)
It can use natural language - pythin to do analysis on data.
"""
import os
from datetime import date
from google.genai import types
from google.adk.agents import Agent
from .prompts import return_instructions_data_analysis
from .tools import call_db_query_agent, call_data_analyzer_agent
from google.adk.agents.callback_context import CallbackContext
from .sub_agents.bigquery.tools import (
    get_database_settings as get_bq_database_settings,
)
date_today = date.today()


def setup_before_agent_call(callback_context: CallbackContext):
    """Setup the agent."""

    if "database_settings" not in callback_context.state:
        db_settings = dict()
        db_settings["use_database"] = "BigQuery"
        callback_context.state["all_db_settings"] = db_settings

    if callback_context.state["all_db_settings"]["use_database"] == "BigQuery":
        callback_context.state["database_settings"] = get_bq_database_settings()
        schema = callback_context.state["database_settings"]["bq_ddl_schema"]

        callback_context._invocation_context.agent.instruction = (
            return_instructions_data_analysis()
            + f"""

    --------- The BigQuery schema of the relevant data with a few sample rows. ---------
    {schema}

    """
        )


data_analysis_agent = Agent(
    model=os.getenv("GENERIC_MODEL"),
    name="data_analysis_agent",
    instruction=return_instructions_data_analysis(),
    before_agent_callback=setup_before_agent_call,
    global_instruction=(
        f"""
        You are a Data Science and Data Analytics Multi Agent System.
        Todays date: {date_today}
        """
    ),
    tools=[call_db_query_agent,call_data_analyzer_agent],
    generate_content_config=types.GenerateContentConfig(temperature=0.01),
)
