"""Integration tests for app/main.py — requires MCP server running on http://127.0.0.1:9000/mcp."""

import pytest
import httpx
from httpx import AsyncClient, ASGITransport

from main import app
from mcp.config import SERVER_URL

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MCP_SERVER_URL = SERVER_URL
AGENT_URL = "http://test"


# ---------------------------------------------------------------------------
# Session-scoped fixture: verify MCP server is reachable before all tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def require_mcp_server():
    """Check MCP server is up. Fail entire suite with clear message if not."""
    try:
        # fastmcp StreamableHTTP responds to any HTTP request on /mcp
        # A GET returns 405 (method not allowed) but confirms the server is up
        response = httpx.get(MCP_SERVER_URL, timeout=3)
        assert response.status_code in (200, 202, 400, 405, 406)
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        pytest.fail(
            f"MCP server is NOT running at {MCP_SERVER_URL}. "
            f"Start it with: python mcp/server.py\nError: {e}"
        )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _post(client: AsyncClient, payload: dict) -> tuple[int, dict]:
    response = await client.post("/agent-task", json=payload)
    return response.status_code, response.json()


def _make_client(raise_exceptions: bool = True) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=raise_exceptions),
        base_url=AGENT_URL,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_check_tool_success():
    """tool_health_check returns 200 with expected text result."""
    async with _make_client() as client:
        status, body = await _post(
            client,
            {"tool_name": "tool_health_check", "arguments": {}},
        )

    assert status == 200
    assert "trace_id" in body
    assert len(body["trace_id"]) == 32

    # result is serialized CallToolResult — check the data field
    result = body["result"]
    assert isinstance(result, dict)
    assert "healthy" in result.get("data", "").lower()


@pytest.mark.asyncio
async def test_health_check_tool_trace_id_unique():
    """Each call to tool_health_check produces a unique trace_id."""
    async with _make_client() as client:
        _, body1 = await _post(client, {"tool_name": "tool_health_check", "arguments": {}})
        _, body2 = await _post(client, {"tool_name": "tool_health_check", "arguments": {}})

    assert body1["trace_id"] != body2["trace_id"]


@pytest.mark.asyncio
async def test_unknown_tool_returns_error():
    """Calling a non-existent tool raises an exception propagated as 500."""
    with pytest.raises(Exception, match="Unknown tool"):
        async with _make_client() as client:
            await _post(
                client,
                {"tool_name": "non_existent_tool", "arguments": {}},
            )


@pytest.mark.asyncio
async def test_missing_tool_name_returns_422():
    """Request without tool_name returns 422 — FastAPI validation."""
    async with _make_client() as client:
        status, _ = await _post(client, {"arguments": {}})

    assert status == 422


@pytest.mark.asyncio
async def test_missing_arguments_returns_422():
    """Request without arguments returns 422 — FastAPI validation."""
    async with _make_client() as client:
        status, _ = await _post(client, {"tool_name": "tool_health_check"})

    assert status == 422


@pytest.mark.asyncio
async def test_health_check_response_structure():
    """Response body strictly matches AgentTaskResponse schema."""
    async with _make_client() as client:
        status, body = await _post(
            client,
            {"tool_name": "tool_health_check", "arguments": {}},
        )

    assert status == 200
    assert set(body.keys()) == {"trace_id", "result"}
    assert isinstance(body["trace_id"], str)
    assert body["result"] is not None
    assert "data" in body["result"]  # CallToolResult serialized field
