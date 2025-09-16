import os
import logging

import google.auth
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app

try:
    from google.cloud import logging as google_cloud_logging
except Exception:  
    google_cloud_logging = None

try:
    from vertexai import agent_engines
except Exception: 
    agent_engines = None

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, export

from app.utils.gcs import create_bucket_if_not_exists
from app.utils.tracing import CloudTraceLoggingSpanExporter
from app.utils.typing import Feedback
from app.utils.load_env_vars import load_env_vars

ENV_FILE = os.getenv("ENV_FILE", "env_vars.txt")
load_env_vars(ENV_FILE)  

os.environ.setdefault("GENERIC_MODEL", "gemini-2.5-flash")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "1")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")


logger = logging.getLogger("promosphere")
logger.setLevel(logging.INFO)

project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
try:
    # Try to infer project from ADC if not set
    if not project_id:
        _, project_id = google.auth.default()
except Exception:
    # Keep project_id as env or None; don't crash
    pass

if google_cloud_logging and project_id:
    try:
        logging_client = google_cloud_logging.Client(project=project_id)
        logging_client.setup_logging()  # route std logging to Cloud Logging
        logger.info("[startup] Cloud Logging is enabled")
    except Exception as e:  # pragma: no cover
        logger.warning("[startup] Cloud Logging init failed: %s", e)

if project_id:
    bucket_uri = f"gs://{project_id}-promosphere-logs-data"
    try:
        create_bucket_if_not_exists(
            bucket_name=bucket_uri,
            project=project_id,
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )
        logger.info("[startup] Artifact bucket ready: %s", bucket_uri)
    except Exception as e:
        logger.warning("[startup] Could not ensure bucket %s: %s", bucket_uri, e)
else:
    bucket_uri = None
    logger.warning("[startup] GOOGLE_CLOUD_PROJECT not set; skipping bucket creation")


try:
    provider = TracerProvider()
    processor = export.BatchSpanProcessor(CloudTraceLoggingSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    logger.info("[startup] OpenTelemetry tracing configured")
except Exception as e:  
    logger.warning("[startup] Tracing setup failed: %s", e)


use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "0") == "1"
agent_engine = None
session_service_uri = None

if use_vertex and agent_engines and project_id:
    try:
        agent_name = os.environ.get("AGENT_ENGINE_SESSION_NAME", "promosphere")
        existing = list(agent_engines.list(filter=f"display_name={agent_name}"))
        if existing:
            agent_engine = existing[0]
            logger.info("[startup] Reusing AgentEngine: %s", agent_engine.resource_name)
        else:
            agent_engine = agent_engines.create(display_name=agent_name)
            logger.info("[startup] Created AgentEngine: %s", agent_engine.resource_name)

        session_service_uri = f"agentengine://{agent_engine.resource_name}"
    except Exception as e:
        logger.warning(
            "[startup] Vertex AgentEngine unavailable, continuing without it: %s", e
        )
else:
    if use_vertex and not agent_engines:
        logger.warning("[startup] vertexai.agent_engines not importable; skipping")
    elif use_vertex and not project_id:
        logger.warning("[startup] GOOGLE_CLOUD_PROJECT missing; skipping AgentEngine")
    else:
        logger.info("[startup] GOOGLE_GENAI_USE_VERTEXAI=0; AgentEngine disabled")

allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)


AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=bucket_uri,  
    allow_origins=allow_origins,
    session_service_uri=session_service_uri, 
)

app.title = "promosphere"
app.description = "API for interacting with the Agent promosphere"


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback."""
    try:
        logger.info("feedback: %s", feedback.model_dump())
        return {"status": "success"}
    except Exception as e:
        logger.warning("feedback logging failed: %s", e)
        return {"status": "ok"}  


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)