import asyncio
import time
from typing import Optional, Union

from fastmcp import Client
from langchain_mcp_adapters.tools import load_mcp_tools
from opentelemetry.trace import Status, StatusCode

import logging

from mcp_local.config import SERVER_URL
from observability import (
    build_propagation_meta,
    get_meter,
    get_tracer,
    init_observability,
    instrument_httpx_client,
    set_span_correlation,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s\n-\n%(message)s",
)

init_observability(service_name="mcp-client")
instrument_httpx_client()

_tracer = get_tracer(__name__)
_meter = get_meter(__name__)

_mcp_calls_total = _meter.create_counter(
    name="mcp_client_calls_total",
    description="Total MCP client calls",
)
_mcp_errors_total = _meter.create_counter(
    name="mcp_client_errors_total",
    description="Total MCP client errors",
)
_mcp_call_latency_ms = _meter.create_histogram(
    name="mcp_client_call_latency_ms",
    description="MCP client call latency in milliseconds",
    unit="ms",
)


class MCPClient:
    """MCP tool runner using fastmcp async client."""

    def __init__(self, base_url: str) -> None:
        self._client = Client(base_url)

    async def list_tools_output_by_session(self):
        """
        Helper method to list tools with logging. We return a _client.session object and use load_mcp_tools
        to convert to langchain suitable tool
        """

        start = time.perf_counter()
        attrs = {"component": "mcp_client", "operation": "list_tools"}
        with _tracer.start_as_current_span("mcp_client.list_tools") as span:
            try:
                # Convert the MCP tool to LangChain StructuredTool
                async with self._client:
                    session = self._client.session
                    lc_tools = await load_mcp_tools(session)
                    _mcp_calls_total.add(1, attributes=attrs)
                    return lc_tools
            except Exception as e:
                _mcp_errors_total.add(1, attributes=attrs)
                span.set_status(Status(StatusCode.ERROR))
                logging.error(f"list_tools_output_by_session failed: {e}")
                raise
            finally:
                _mcp_call_latency_ms.record(
                    (time.perf_counter() - start) * 1000,
                    attributes=attrs,
                )

        # try:
        #     async with self._client:
        #         result =  await self._client.list_tools()
        #         logging.info(f"list_tools_output: {result}")
        #         return result
        # except Exception as e:
        #     logging.error(f"list_tools_output failed: {e}")
        #     raise

    @staticmethod
    def _build_tool_payload(
        trace_id: str,
        mcp_name: str,
        call_type: Union["tool", "resource", "prompt"],
        arguments: Optional[dict] = None,
    ) -> tuple[str, dict, str]:
        """Build and log tool call payload with tracing.

        Args:
            trace_id: Trace identifier for logging.
            mcp_name: Registered MCP tool name.
            arguments: Flexible input arguments.

        Returns:
            Tuple of (tool_name, arguments).
        """

        logging.info(f"[{trace_id}] Building payload for {call_type}: {mcp_name}")

        # TODO: Implement tracing logic and history management here later

        return mcp_name, arguments, call_type

    @staticmethod
    async def check(self):
        """Run MCP client demo: ping, list, call tool, read resource."""
        async with self.client:
            await self.client.ping()
            logging.info("ping: OK")

            result = await self.client.list_tools()
            logging.info(f"list_tools: {result}")

            result = await self.client.list_prompts()
            logging.info(f"list_prompts: {result}")

            result = await self.client.list_resources()
            logging.info(f"list_resources: {result}")

    # tool, resource, prompt method use from fastapi gateway to orchestrator
    async def run_client(
        self,
        trace_id: str,
        mcp_name: str,
        call_type: Union["tool", "resource", "prompt"],
        arguments: Optional[dict] = None,
    ):
        """Execute a tool via MCP call_tool."""

        # Fix empty dict input
        arguments = arguments or {}

        name, args, call_type = self._build_tool_payload(
            trace_id, mcp_name, call_type, arguments
        )
        attrs = {
            "mcp.name": mcp_name,
            "mcp.call_type": call_type,
        }
        meta = build_propagation_meta(trace_id)
        start = time.perf_counter()

        with _tracer.start_as_current_span("mcp_client.run_client") as span:
            set_span_correlation(span, trace_id)
            span.set_attribute("mcp.name", mcp_name)
            span.set_attribute("mcp.call_type", call_type)
            span.add_event("mcp.call.started")
            try:
                if call_type == "tool":
                    async with self._client:
                        try:
                            result = await self._client.call_tool(
                                name,
                                args,
                                timeout=5,
                                meta=meta,
                            )
                            _mcp_calls_total.add(1, attributes=attrs)
                            span.add_event("mcp.call.succeeded")
                            logging.info(f"[{trace_id}] run_tool/{mcp_name}: {result}")
                            return {
                                "trace_id": trace_id,
                                "result": result,
                            }
                        except Exception as e:
                            _mcp_errors_total.add(1, attributes=attrs)
                            span.set_status(Status(StatusCode.ERROR))
                            span.add_event("mcp.call.failed")
                            logging.error(
                                f"[{trace_id}] run_tool/tool/{mcp_name} failed: {e}"
                            )
                            raise

                if call_type == "resource":
                    async with self._client:
                        try:
                            result = await self._client.read_resource(
                                uri=mcp_name,
                                meta=meta,
                            )
                            _mcp_calls_total.add(1, attributes=attrs)
                            span.add_event("mcp.call.succeeded")
                            logging.info(
                                f"[{trace_id}] run_tool/resource/{mcp_name}: {result}"
                            )
                            return {
                                "trace_id": trace_id,
                                "result": result,
                            }
                        except Exception as e:
                            _mcp_errors_total.add(1, attributes=attrs)
                            span.set_status(Status(StatusCode.ERROR))
                            span.add_event("mcp.call.failed")
                            logging.error(
                                f"[{trace_id}] run_tool/resource/{mcp_name} failed: {e}"
                            )
                            raise

                if call_type == "prompt":
                    async with self._client:
                        try:
                            result = await self._client.get_prompt(
                                mcp_name,
                                arguments={"trace_id": trace_id},
                                meta=meta,
                            )
                            _mcp_calls_total.add(1, attributes=attrs)
                            span.add_event("mcp.call.succeeded")
                            logging.info(
                                f"[{trace_id}] run_tool/prompt/{mcp_name}: {result}"
                            )
                            return {
                                "trace_id": trace_id,
                                "result": result,
                            }
                        except Exception as e:
                            _mcp_errors_total.add(1, attributes=attrs)
                            span.set_status(Status(StatusCode.ERROR))
                            span.add_event("mcp.call.failed")
                            logging.error(
                                f"[{trace_id}] run_tool/prompt/{mcp_name} failed: {e}"
                            )
                            raise

                _mcp_errors_total.add(1, attributes=attrs)
                logging.error(f"[{trace_id}] Invalid call_type: {call_type}")
                raise ValueError(f"Invalid call_type: {call_type}")
            finally:
                _mcp_call_latency_ms.record(
                    (time.perf_counter() - start) * 1000,
                    attributes=attrs,
                )


if __name__ == "__main__":
    # Test code to run the MCP client and execute a tool call
    client_obj = MCPClient(base_url=SERVER_URL)

    # We run the async function inside asyncio with handle it in parallel
    output = asyncio.run(
        client_obj.run_client("trace-123", "tool_health_check", "tool")
    )
    logging.info(f"Tool execution result: {output}")
