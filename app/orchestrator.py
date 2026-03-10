"""
This module contains code to orchestrate the execution of the LLM agent
"""
import asyncio
import logging
import operator
from typing import Literal
from dotenv import load_dotenv
from langchain_core.tools import StructuredTool

from langchain_google_genai import GoogleGenerativeAI, ChatGoogleGenerativeAI
from langchain_mcp_adapters.tools import load_mcp_tools
from pydantic import create_model

from core.config import LLM_MODEL, LLM_TEMPERATURE
from langchain.chat_models import init_chat_model
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.constants import START, END
from typing_extensions import Annotated, TypedDict
from langgraph.graph import StateGraph

from mcp_local.client import MCPClient
from mcp_local.config import SERVER_URL

load_dotenv(verbose=True)

# MCP client — single instance shared across nodes #
mcp_client = MCPClient(base_url=SERVER_URL)


# LLM #
model_raw = ChatGoogleGenerativeAI(
    model= LLM_MODEL,
    temperature= LLM_TEMPERATURE
)


# State #
class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int
    trace_id: str


# Nodes #
async def llm_node(state: MessagesState) -> dict:
    """LLM decides whether to call a tool or not."""

    # Get the latest raw tool list from the mcp server at each run
    tools = await mcp_client.list_tools_output_by_session()  # fetch the latest tools from MCP server
    model = model_raw.bind_tools(tools)

    # Attach the system prompt with dynamic tool description
    # See mcp_local/client.py/run_client () for details on the input  structure
    prompt_response = await mcp_client.run_client(
        trace_id=state["trace_id"], mcp_name="system_prompt", call_type="prompt"
    )
    # Getting the system prompt from the mcp interface. Be super careful while handling the return objects
    system_text: str = prompt_response["result"].messages[0].content.text

    return {
        "messages": [
            await model.ainvoke(
                [SystemMessage(content=system_text)]
                + state["messages"]
            )
        ],
        "llm_calls": state.get("llm_calls", 0) + 1,
        "trace_id": state.get("trace_id", "trace_id not set"),
    }

async def tool_node(state: MessagesState) -> dict[str, list[ToolMessage]]:
    """Performs MCP tool calls for all tool_calls in the last message."""

    trace_id: str = state.get("trace_id", "unknown")
    results: list[ToolMessage] = []

    for tool_call in state["messages"][-1].tool_calls:
        tool_name: str = tool_call["name"]
        tool_args: dict = tool_call["args"]
        tool_call_id: str = tool_call["id"]

        try:
            response = await mcp_client.run_client(
                trace_id=trace_id,
                mcp_name=tool_name,
                call_type="tool",
                arguments=tool_args,
            )
            content = str(response["result"].content[0].text)
            logging.info(f"[{trace_id}] tool_node/{tool_name}: OK")
        except Exception as e:
            content = f"Tool '{tool_name}' failed: {e}"
            logging.error(f"[{trace_id}] tool_node/{tool_name} error: {e}")

        results.append(ToolMessage(content=content, tool_call_id=tool_call_id))

    return {"messages": results}

def should_continue(state: MessagesState) -> Literal["tool_node", "__end__"]:
    """Decide if we should continue the loop or stop based upon whether the LLM made a tool call"""

    messages = state["messages"]
    last_message = messages[-1]

    # If the LLM makes a tool call, then perform an action
    if last_message.tool_calls:
        return "tool_node"

    # Otherwise, we stop orchestration
    return END


# Edges #
agent_builder = StateGraph(MessagesState)

# Add nodes
agent_builder.add_node("llm_node", llm_node)
agent_builder.add_node("tool_node", tool_node)

# Add edges to connect nodes
agent_builder.add_edge(START, "llm_node")
agent_builder.add_conditional_edges(
    "llm_node",
    should_continue,
    ["tool_node", END]  # choices that should_continue can return
)
agent_builder.add_edge("tool_node", "llm_node")  # connect tool_node back to llm_node to create a loop

# Compile the agent
agent = agent_builder.compile()


async def run_agent(message: str, trace_id: str) -> str:
    """Run the agent graph with a user message and return the final response.

    Args:
        message: The user message to process.
        trace_id: Trace identifier passed from the gateway for end-to-end logging.

    Returns:
        The final assistant response as a string.
    """
    result = await agent.ainvoke({
        "messages": [HumanMessage(content=message)],
        "trace_id": trace_id,
        "llm_calls": 0,
    })
    return str(result["messages"][-1].content)


if __name__ == "__main__":
    asyncio.run(run_agent(
        message="call health_check_tool and then name the tools available to you",
        trace_id="test-trace-123",
    ))





