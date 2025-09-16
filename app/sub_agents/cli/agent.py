"""CLI Agent: runs cli commands."""

import os
from google.adk.agents import Agent
from google.genai import types

from .prompts import return_instructions_cli_agent
from .tools import cli_run_tool, cli_gcloud_tool, call_search_agent
# from google.adk.tools import google_search

RESOURCES_PROJECT=os.getenv("RESOURCES_PROJECT")
RESOURCES_LOCATION=os.getenv("RESOURCES_LOCATION")

cli_agent = Agent(
    model=os.getenv("ADVANCED_MODEL"),
    name="cli_agent",
    instruction=return_instructions_cli_agent(resources_project=RESOURCES_PROJECT, resources_location=RESOURCES_LOCATION),
    tools=[cli_run_tool, cli_gcloud_tool, call_search_agent],
    generate_content_config=types.GenerateContentConfig(temperature=0.01),
)