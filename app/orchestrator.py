"""
This module contains code to orchestrate the execution of the LLM agent
"""

import asyncio
import logging
from typing import Literal

from dotenv import load_dotenv
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.pregel.debug import RunnableConfig
from typing_extensions import Annotated, TypedDict

from core.config import (
    LLM_MODEL,
    LLM_TEMPERATURE,
    MESSAGES_BUFFER_LTM,
    SUMMARISE_MESSAGE_THRESHOLD,
    get_short_term_memory_config
)
from mcp_local.client import MCPClient
from mcp_local.config import SERVER_URL
from memory.long_term import LongTermMemory
from memory.short_term import get_short_term_memory

load_dotenv(verbose=True)

# MCP client — single instance shared across nodes #
mcp_client = MCPClient(base_url=SERVER_URL)

# Long-term memory instance #
long_term_memory = LongTermMemory()


# State #
class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    summary: str | None
    llm_calls: int
    trace_id: str


# Nodes #


async def llm_node(state: MessagesState) -> dict:
    """LLM decides whether to call a tool or not."""

    # LLM #
    model_raw = ChatGoogleGenerativeAI(model=LLM_MODEL, temperature=LLM_TEMPERATURE)

    # Get the latest raw tool list from the mcp server at each run
    # mcp tools are converted to langchain compatible tools
    tools = (
        await mcp_client.list_tools_output_by_session()
    )  # fetch the latest tools from MCP server
    model = model_raw.bind_tools(tools)

    # Attach the system prompt with dynamic tool description
    # See mcp_local/client.py/run_client () for details on the input structure
    prompt_response = await mcp_client.run_client(
        trace_id=state["trace_id"], mcp_name="system_prompt", call_type="prompt"
    )
    # Getting the system prompt from the mcp interface.
    system_text: str = prompt_response["result"].messages[0].content.text

    # --- LONG TERM MEMORY RETRIEVAL ---
    # Retrieve relevant past context if available
    latest_user_message = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None
    )

    past_context_str = ""
    if latest_user_message:
        # Search for relevant summaries based on user input
        relevant_docs = long_term_memory.search(query=latest_user_message.content, k=2)
        if relevant_docs:
            past_context_str = "\n\nRelevant Past Context:\n" + "\n".join(
                [f"- {doc.page_content}" for doc in relevant_docs]
            )
            logging.info(
                f"[{state['trace_id']}] Retrieved {len(relevant_docs)} past memories."
            )

    # Append past context to system prompt
    full_system_text = system_text + past_context_str

    return {
        "messages": [
            await model.ainvoke(
                [SystemMessage(content=full_system_text)] + state["messages"]
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
            # Robustly handle MCP response structure
            if response.get("result") and response["result"].content:
                content = str(response["result"].content[0].text)
            else:
                content = str(response)

            logging.info(f"[{trace_id}] tool_node/{tool_name}: OK")
        except Exception as e:
            content = f"Tool '{tool_name}' failed: {e}"
            logging.error(f"[{trace_id}] tool_node/{tool_name} error: {e}")

        results.append(ToolMessage(content=content, tool_call_id=tool_call_id))

    return {"messages": results}


async def summarize_node(state: MessagesState) -> dict:
    """Summarizes the conversation and prunes old messages."""

    # trace_id is critical, you need that
    try:
        trace_id = state.get("trace_id")
    except KeyError:
        logging.warning(
            "trace_id not found in state during summarization. Defaulting to 'unknown'."
        )
        exit(1)

    logging.info(
        f"[{trace_id}] Triggering summarization (message count: {len(state['messages'])})"
    )

    # Independent summary model
    model = ChatGoogleGenerativeAI(model=LLM_MODEL, temperature=0)

    # Get summary prompt from MCP
    result = await mcp_client.run_client(
        trace_id=trace_id, mcp_name="summary_prompt", call_type="prompt"
    )
    summary_prompt = result["result"].messages[0].content.text

    # Invoke model with current message history + summary prompt
    messages = state["messages"] + [HumanMessage(content=summary_prompt)]
    
    # Summarization
    response = await model.ainvoke(messages)
    summary_text = response.content

    # Handle list content (common with Gemini)
    if isinstance(summary_text, list):
        summary_text = " ".join(
            [
                part if isinstance(part, str) else part.get("text", "")
                for part in summary_text
            ]
        )

    # Store in Long Term Memory (ChromaDB)
    if summary_text:
        # Create a parallel fire and leave thread
        asyncio.create_task(
            long_term_memory.store_async(
                text=summary_text, metadata={"trace_id": trace_id}
            )
        )
    
    # Pruning
    # Prune old messages to keep context window manageable
    # We keep the last 2 messages (usually query + answer) and remove the rest
    # Note: We must be careful not to delete the very last message if it's the one we just generated in llm_node
    # But this node runs AFTER tool_node or llm_node, so it should be safe.

    messages_to_keep = MESSAGES_BUFFER_LTM  # Keep a small buffer
    if len(state["messages"]) > messages_to_keep:
        messages_to_delete = state["messages"][:-messages_to_keep]

        delete_ops = [RemoveMessage(id=m.id) for m in messages_to_delete]  # type: ignore

        logging.info(f"[{trace_id}] Pruning {len(delete_ops)} old messages.")
        return {
            "messages": delete_ops,
            "summary": summary_text,  # Update state with latest summary
        }

    return {"summary": summary_text}


def should_continue(
    state: MessagesState,
) -> Literal["tool_node", "summarize_node", "__end__"]:
    """Decide if we should continue the loop or stop based upon whether the LLM made a tool call"""

    messages = state["messages"]
    last_message = messages[-1]

    # If the LLM makes a tool call, then perform an action
    if last_message.tool_calls:  # type:ignore
        return "tool_node"

    # If message history is too long, trigger summarization
    # Threshold set to 10 for testing purposes (normally 20-50)
    if len(messages) > SUMMARISE_MESSAGE_THRESHOLD:
        return "summarize_node"

    # Otherwise, we stop orchestration
    return END


# Edges #
agent_builder = StateGraph(MessagesState)

# Add nodes
agent_builder.add_node("llm_node", llm_node)
agent_builder.add_node("tool_node", tool_node)
agent_builder.add_node("summarize_node", summarize_node)

# Add edges to connect nodes
agent_builder.add_edge(START, "llm_node")
agent_builder.add_conditional_edges(
    "llm_node",
    should_continue,
    ["tool_node", "summarize_node", END],  # choices that should_continue can return
)
agent_builder.add_edge("tool_node", "llm_node")
agent_builder.add_edge("summarize_node", END)  # End after summarizing


async def run_agent(message: str, trace_id: str) -> str:
    """Run the agent graph with a user message and return the final response.

    Args:
        message: The user message to process.
        trace_id: Trace identifier passed from the gateway for end-to-end logging.

    Returns:
        The final assistant response as a string.
    """

    # Compile the agent after yielding a redis checkpointer
    async with get_short_term_memory() as checkpointer:
        # Compile the agent with the checkpointer
        agent = agent_builder.compile(checkpointer=checkpointer)

        # Define config
        config: RunnableConfig = get_short_term_memory_config(thread_id=trace_id)

        result = await agent.ainvoke(
            {
                "messages": [HumanMessage(content=message)],
                "trace_id": trace_id,
                "llm_calls": 0,
            },
            config=config,  # use trace_id to identify the same conversation thread in short term memory
        )
        return str(result["messages"][-1].content)


if __name__ == "__main__":
    pass
    # async def main():
    #     print("-" * 50)
    #     print("Test 1: Setting memory")
    #     print("-" * 50)
    #     res1 = await run_agent(
    #         message="my name is bob",
    #         trace_id="test-trace-123",
    #     )
    #     print(f"Agent Response 1: {res1}\n")

    #     print("-" * 50)
    #     print("Test 2: Retrieving memory")
    #     print("-" * 50)
    #     res2 = await run_agent(
    #         message="what is my name?",
    #         trace_id="test-trace-123",
    #     )
    #     print(f"Agent Response 2: {res2}")
    #     print("-" * 50)

    # asyncio.run(main())
