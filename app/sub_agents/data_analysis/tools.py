"""
-- it get data from database (BQ) using NL2SQL
-- then, it use NL2Py to do further data analysis as needed
"""

from google.adk.tools import ToolContext
from google.adk.tools.agent_tool import AgentTool

from .sub_agents import data_analyzer_agent, db_query_agent


async def call_db_query_agent(
    question: str,
    tool_context: ToolContext,
):
    """Tool to call database (natural language to SQL) agent."""

    print("db agent called with question = " + question)

    print(
        "\n call_db_query_agent.use_database:"
        f' {tool_context.state["all_db_settings"]["use_database"]}'
    )

    agent_tool = AgentTool(agent=db_query_agent)

    db_query_agent_output = await agent_tool.run_async(
        args={"request": question}, tool_context=tool_context
    )

    tool_context.state["db_query_agent_output"] = db_query_agent_output
    print("db agent output = " + db_query_agent_output)
    return db_query_agent_output


async def call_data_analyzer_agent(
    question: str,
    tool_context: ToolContext,
):
    """Tool to call data analytics (Natural language to python) agent."""

    # Fast path: DS agent not needed, just echo DB output.
    if question == "N/A":
        print("question is NA, using db agent output")
        db_out = tool_context.state.get("db_query_agent_output", "")
        print("using this db agent output = " + str(db_out))
        return db_out

    print("question is not na = " + question)

    # SAFELY read query_result from state (may be absent or empty)
    input_data = tool_context.state.get("query_result")

    if input_data is None:
        # No query_result was set. This means the DB/validation step didn't run,
        # failed, or didn’t write to state. Avoid crashing; return a clear message.
        db_out = tool_context.state.get("db_query_agent_output", "")
        msg = (
            "No `query_result` found in state. "
            "This typically happens if the DB validation/query step did not run "
            "or returned no data. Skipping Python analysis."
        )
        print(msg)
        # Prefer returning something useful to the caller (e.g., DB agent output)
        return db_out or msg

    if isinstance(input_data, list) and len(input_data) == 0:
        # Query executed but returned 0 rows; skip analysis.
        db_out = tool_context.state.get("db_query_agent_output", "")
        msg = (
            "Query executed successfully but returned 0 rows. "
            "Skipping Python analysis."
        )
        print(msg)
        return db_out or msg

    question_with_data = f"""
  Question to answer: {question}

  Actual data to analyze for the previous question is below (JSON-like rows):
  {input_data}
  """

    agent_tool = AgentTool(agent=data_analyzer_agent)
    data_analyzer_agent_output = await agent_tool.run_async(
        args={"request": question_with_data}, tool_context=tool_context
    )
    tool_context.state["data_analyzer_agent_output"] = data_analyzer_agent_output

    print("da agent output = " + str(data_analyzer_agent_output))
    return data_analyzer_agent_output
