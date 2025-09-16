import os
from datetime import date
from google.genai import types
from google.adk.agents import Agent
from .prompts import return_instructions_root

date_today = date.today()
project = os.getenv("RESOURCES_PROJECT")
location = os.getenv("RESOURCES_LOCATION")

root_agent = Agent(
    model=os.getenv("GENERIC_MODEL"),
    name="promosphere",
    instruction=return_instructions_root(),
    global_instruction=f"""
    You are PromoSphere, a specialized assistant that helps businesses create, monitor, and optimize marketing campaigns.
    You focus on campaign performance, ROI, and customer impact by analyzing data from BigQuery and related sources.
    You provide clear insights, actionable recommendations.
    Today's date: {date_today}
    """,
    tools=[],
    generate_content_config=types.GenerateContentConfig(temperature=0.01),
)
