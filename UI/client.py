import os
from typing import Any

import httpx
from dotenv import load_dotenv

from UI.models import AgentTaskResult


load_dotenv()


def _get_gateway_base_url() -> str:
    raw = os.getenv("GATEWAY_URL", "http://localhost:8001")
    value = raw.strip().strip('"').strip("'")
    if not value:
        return "http://localhost:8001"
    return value.rstrip("/")


def _get_timeout_seconds() -> float:
    raw = os.getenv("GATEWAY_UI_TIMEOUT", "60").strip().strip('"').strip("'")
    try:
        timeout = float(raw)
    except ValueError:
        return 60.0
    if timeout <= 0:
        return 60.0
    return timeout


def _extract_result_text(result: Any) -> str:
    if isinstance(result, str):
        return result
    return str(result)


class GatewayClient:
    def __init__(self) -> None:
        self.base_url = _get_gateway_base_url()
        self.timeout_seconds = _get_timeout_seconds()

    async def send_message(self, message: str) -> AgentTaskResult:
        payload = {"message": message}
        endpoint = f"{self.base_url}/agent-task"

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(endpoint, json=payload)
            response.raise_for_status()

        data = response.json()
        trace_id = str(data.get("trace_id", ""))
        result_text = _extract_result_text(data.get("result"))
        return AgentTaskResult(trace_id=trace_id, result=result_text)
