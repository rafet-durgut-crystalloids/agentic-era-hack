import os
from datetime import date

os.environ["RESOURCES_LOCATION"] = "us-central1"
os.environ["GOOGLE_CLOUD_PROJECT"] = "qwiklabs-gcp-00-2a88a82239a1"
os.environ["GENERIC_MODEL"] = "gemini-2.5-flash"
os.environ["ADVANCED_MODEL"] = "gemini-2.5-pro"
os.environ["FIRESTORE_PROJECT"] = "qwiklabs-gcp-00-2a88a82239a1"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "1"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"
os.environ["BQ_DATA_PROJECT_ID"] = "qwiklabs-gcp-00-2a88a82239a1"
os.environ["BQ_COMPUTE_PROJECT_ID"] = "qwiklabs-gcp-00-2a88a82239a1"
os.environ["BQ_DATASET_ID"] = "business_data"
os.environ["RESOURCES_PROJECT"] = "qwiklabs-gcp-00-2a88a82239a1"
os.environ["BUSINESS_CONFIG_JSON_PROJECT"] = "qwiklabs-gcp-00-2a88a82239a1"
os.environ["BUSINESS_CONFIIG_JSON_BUCKET"] = "config_test0912391"
os.environ["BUSINESS_CONFIIG_JSON_FILE"] = "business_config.json"
os.environ["STRATEGIES_JSON_PROJECT"] = "qwiklabs-gcp-00-2a88a82239a1"
os.environ["STRATEGIES_JSON_BUCKET"] = "config_test0912391"
os.environ["STRATEGIES_JSON_FILE"] = "strategies.json"

date_today = date.today()
project = os.getenv("RESOURCES_PROJECT")
location = os.getenv("RESOURCES_LOCATION")


from google.genai import types
from google.adk.agents import Agent
from .prompts import return_instructions_root
from .tools import call_data_analytics_agent, call_resource_agent, call_search_agent, call_storage_agent



root_agent = Agent(
    model=os.getenv("GENERIC_MODEL"),
    name="promosphere",
    instruction=return_instructions_root(resource_project_id=project, resource_project_location=location),
    global_instruction=f"""
    You are PromoSphere, an assistant for creating, monitoring, and optimizing marketing campaigns.
    Focus on campaign performance, ROI, and customer impact using BigQuery data and related sources.
    Provide clear insights and actionable recommendations.
    Today's date: {date_today}
    """,
    tools=[call_data_analytics_agent, call_resource_agent, call_search_agent, call_storage_agent],
    generate_content_config=types.GenerateContentConfig(temperature=0.3),
)
