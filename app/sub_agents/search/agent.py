import os
from google.adk import Agent
from google.adk.tools import google_search
from .prompts import return_instructions_search_agent

search_agent = Agent(
    name="search_agent",
    model=os.getenv("GENERIC_MODEL"),
    description="Agent to answer questions using Google Search.",
    instruction=return_instructions_search_agent(),
    tools=[google_search]
)