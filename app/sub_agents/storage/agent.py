"""Storage Agent: get or manage data from Google Cloud Storage using available tools."""

import os
from google.adk.agents import Agent
from google.genai import types

from .prompts import return_instructions_storage_agent
from .tools import ALL_STORAGE_TOOLS

storage_agent = Agent(
    model=os.getenv("GENERIC_MODEL"),
    name="storage_agent",
    instruction=return_instructions_storage_agent(),
    tools=ALL_STORAGE_TOOLS,
    generate_content_config=types.GenerateContentConfig(temperature=0.01),
)