import os
from datetime import date
from google.genai import types
from google.adk.agents import Agent
from .prompts import return_instructions_resource_agent
from .tools import ALL_RESOURCE_TOOLS


date_today = date.today()
project = os.getenv("RESOURCES_PROJECT")
location = os.getenv("RESOURCES_LOCATION")

resource_agent = Agent(
    name="resource",
    model=os.getenv("ADVANCED_MODEL"),
    instruction=return_instructions_resource_agent(resource_project_id=project, resource_project_location=location),
    tools=ALL_RESOURCE_TOOLS,
    generate_content_config=types.GenerateContentConfig(temperature=0.01),
)