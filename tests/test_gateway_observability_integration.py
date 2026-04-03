from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_gateway_honors_valid_incoming_trace_id():
    with patch("app.main._get_run_agent", return_value=AsyncMock(return_value="ok")):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/agent-task",
                json={"message": "hello", "trace_id": "valid-trace-12345"},
            )

    assert response.status_code == 200
    assert response.json()["trace_id"] == "valid-trace-12345"


@pytest.mark.asyncio
async def test_gateway_generates_trace_id_for_invalid_input():
    with patch("app.main._get_run_agent", return_value=AsyncMock(return_value="ok")):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/agent-task",
                json={"message": "hello", "trace_id": "bad trace id with spaces"},
            )

    body = response.json()
    assert response.status_code == 200
    assert body["trace_id"] != "bad trace id with spaces"
    assert len(body["trace_id"]) == 32
