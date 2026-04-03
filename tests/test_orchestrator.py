"""
Unit tests for app/orchestrator.py.
MCP client and LLM are fully mocked — no running server required.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_ai_message(content: str = "hello", tool_calls: list | None = None) -> AIMessage:
    msg = AIMessage(content=content)
    msg.tool_calls = tool_calls or []
    return msg


def _make_tool_result_mock(text: str = "ok") -> MagicMock:
    """Mimics the nested structure: result.content[0].text"""
    content_item = MagicMock()
    content_item.text = text
    result = MagicMock()
    result.content = [content_item]
    return result


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def mock_mcp_client():
    """Patch the module-level mcp_client in orchestrator."""
    with patch("app.orchestrator.mcp_client") as mock:
        mock.list_tools_output_by_session = AsyncMock(return_value=[])
        mock.run_client = AsyncMock()
        yield mock


@pytest.fixture()
def mock_model_raw():
    """Patch the module-level model_raw in orchestrator."""
    with patch("app.orchestrator.model_raw") as mock:
        yield mock


# ── should_continue ───────────────────────────────────────────────────────────

class TestShouldContinue:
    def test_should_continue_returns_tool_node_when_tool_calls(self):
        from app.orchestrator import should_continue

        tool_call = {"name": "tool_health_check", "args": {}, "id": "tc-1", "type": "tool_call"}
        state = {"messages": [_make_ai_message(tool_calls=[tool_call])], "llm_calls": 1, "trace_id": "t1"}
        assert should_continue(state) == "tool_node"

    def test_should_continue_returns_end_when_no_tool_calls(self):
        from app.orchestrator import should_continue
        from langgraph.constants import END

        state = {"messages": [_make_ai_message()], "llm_calls": 1, "trace_id": "t1"}
        assert should_continue(state) == END


# ── llm_node ──────────────────────────────────────────────────────────────────

class TestLlmNode:
    @pytest.mark.asyncio
    async def test_llm_node_returns_message_and_increments_calls(
        self, mock_mcp_client, mock_model_raw
    ):
        from app.orchestrator import llm_node

        ai_response = _make_ai_message("final answer")

        # get_prompt returns a mock with .messages[0].content as plain str
        prompt_msg = MagicMock()
        prompt_msg.content = "You are an assistant."
        prompt_result = MagicMock()
        prompt_result.messages = [prompt_msg]
        mock_mcp_client.run_client.return_value = {"trace_id": "t1", "result": prompt_result}

        bound_model = MagicMock()
        bound_model.ainvoke = AsyncMock(return_value=ai_response)
        mock_model_raw.bind_tools.return_value = bound_model

        state = {
            "messages": [HumanMessage(content="ping")],
            "llm_calls": 0,
            "trace_id": "t1",
        }

        result = await llm_node(state)

        assert result["llm_calls"] == 1
        assert result["trace_id"] == "t1"
        assert len(result["messages"]) == 1
        assert result["messages"][0].content == "final answer"

    @pytest.mark.asyncio
    async def test_llm_node_calls_bind_tools_with_mcp_tools(
        self, mock_mcp_client, mock_model_raw
    ):
        from app.orchestrator import llm_node

        fake_tool = MagicMock()
        mock_mcp_client.list_tools_output_by_session.return_value = [fake_tool]

        prompt_msg = MagicMock()
        prompt_msg.content = "system"
        prompt_result = MagicMock()
        prompt_result.messages = [prompt_msg]
        mock_mcp_client.run_client.return_value = {"trace_id": "t2", "result": prompt_result}

        bound_model = MagicMock()
        bound_model.ainvoke = AsyncMock(return_value=_make_ai_message())
        mock_model_raw.bind_tools.return_value = bound_model

        state = {"messages": [HumanMessage(content="hi")], "llm_calls": 0, "trace_id": "t2"}
        await llm_node(state)

        mock_model_raw.bind_tools.assert_called_once_with([fake_tool])


# ── tool_node ─────────────────────────────────────────────────────────────────

class TestToolNode:
    @pytest.mark.asyncio
    async def test_tool_node_returns_tool_message_on_success(self, mock_mcp_client):
        from app.orchestrator import tool_node

        tool_result = _make_tool_result_mock("healthy")
        mock_mcp_client.run_client.return_value = {"trace_id": "t1", "result": tool_result}

        tool_call = {"name": "tool_health_check", "args": {}, "id": "tc-1", "type": "tool_call"}
        state = {
            "messages": [_make_ai_message(tool_calls=[tool_call])],
            "llm_calls": 1,
            "trace_id": "t1",
        }

        result = await tool_node(state)

        assert len(result["messages"]) == 1
        msg = result["messages"][0]
        assert isinstance(msg, ToolMessage)
        assert msg.content == "healthy"
        assert msg.tool_call_id == "tc-1"

    @pytest.mark.asyncio
    async def test_tool_node_returns_error_message_on_failure(self, mock_mcp_client):
        from app.orchestrator import tool_node

        mock_mcp_client.run_client.side_effect = Exception("connection refused")

        tool_call = {"name": "tool_health_check", "args": {}, "id": "tc-2", "type": "tool_call"}
        state = {
            "messages": [_make_ai_message(tool_calls=[tool_call])],
            "llm_calls": 1,
            "trace_id": "t1",
        }

        result = await tool_node(state)

        msg = result["messages"][0]
        assert "failed" in msg.content
        assert "connection refused" in msg.content

    @pytest.mark.asyncio
    async def test_tool_node_handles_multiple_tool_calls(self, mock_mcp_client):
        from app.orchestrator import tool_node

        tool_result = _make_tool_result_mock("ok")
        mock_mcp_client.run_client.return_value = {"trace_id": "t1", "result": tool_result}

        tool_calls = [
            {"name": "tool_a", "args": {"x": 1}, "id": "tc-a", "type": "tool_call"},
            {"name": "tool_b", "args": {}, "id": "tc-b", "type": "tool_call"},
        ]
        state = {
            "messages": [_make_ai_message(tool_calls=tool_calls)],
            "llm_calls": 1,
            "trace_id": "t1",
        }

        result = await tool_node(state)

        assert len(result["messages"]) == 2
        assert mock_mcp_client.run_client.call_count == 2


# ── run_agent ─────────────────────────────────────────────────────────────────

class TestRunAgent:
    @pytest.mark.asyncio
    async def test_run_agent_returns_final_response(self, mock_mcp_client, mock_model_raw):
        from app.orchestrator import run_agent

        prompt_msg = MagicMock()
        prompt_msg.content = "system"
        prompt_result = MagicMock()
        prompt_result.messages = [prompt_msg]
        mock_mcp_client.run_client.return_value = {"trace_id": "t1", "result": prompt_result}

        bound_model = MagicMock()
        bound_model.ainvoke = AsyncMock(return_value=_make_ai_message("done"))
        mock_model_raw.bind_tools.return_value = bound_model

        response = await run_agent("say hello", trace_id="t1")

        assert isinstance(response, str)
        assert "done" in response

    @pytest.mark.asyncio
    async def test_run_agent_uses_provided_trace_id(self, mock_mcp_client, mock_model_raw):
        from app.orchestrator import run_agent

        prompt_msg = MagicMock()
        prompt_msg.content = "system"
        prompt_result = MagicMock()
        prompt_result.messages = [prompt_msg]
        mock_mcp_client.run_client.return_value = {"trace_id": "trace-xyz", "result": prompt_result}

        bound_model = MagicMock()
        bound_model.ainvoke = AsyncMock(return_value=_make_ai_message("ok"))
        mock_model_raw.bind_tools.return_value = bound_model

        await run_agent("test", trace_id="trace-xyz")

        # trace_id propagated to run_client calls
        for call in mock_mcp_client.run_client.call_args_list:
            assert call.kwargs.get("trace_id") == "trace-xyz" or call.args[0] == "trace-xyz"

# class TestMessageInvoke:
#
#     async def test_message_invoke_returns_message(self, mock_mcp_client, mock_model_raw):
#         from app.orchestrator import agent
#
#         response = agent.invoke({
#         "messages": [HumanMessage(content="Call tool_health_check")],
#         "trace_id": "test123",
#         "llm_calls": 0,
#     })
#
#         assert isinstance(response, AIMessage)


