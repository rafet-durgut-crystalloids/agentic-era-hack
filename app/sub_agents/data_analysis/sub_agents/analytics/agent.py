"""Generate natural language to python and use code interpreter to run the generated code."""
import os
from google.adk.code_executors import VertexAiCodeExecutor
from google.adk.agents import Agent
from .prompts import return_instructions_analytics


analytics_agent = Agent(
    model=os.getenv("GENERIC_MODEL"),
    name="analytics_agent",
    instruction=return_instructions_analytics(),
    code_executor=VertexAiCodeExecutor(
        optimize_data_file=True,
        stateful=True
    ),
)
