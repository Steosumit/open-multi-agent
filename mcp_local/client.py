import asyncio
import logging
import pathlib
import time
from typing import Optional, Union

import yaml
from fastmcp import Client
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport
from langchain_mcp_adapters.tools import load_mcp_tools
from opentelemetry.trace import Status, StatusCode

from mcp_local.config import SERVER_URL
from observability import (
    build_propagation_meta,
    get_meter,
    get_tracer,
    init_observability,
    instrument_httpx_client,
    set_span_correlation,
)


def load_servers_config() -> list[dict]:
    """Load MCP servers from servers.yaml config file."""
    config_path = pathlib.Path(__file__).parent / "servers.yaml"
    if config_path.exists():
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
            return config.get("servers", [])
    return []


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
    """MCP tool runner using fastmcp async client. Supports multiple servers."""

    def __init__(self, base_url: str, servers_config: list[dict] | None = None) -> None:
        self._default_client = Client(StreamableHttpTransport(url=base_url))
        self._servers: dict[str, Client] = {}

        # Dynamically add servers from config
        if servers_config:
            for server in servers_config:
                self.add_server(server["name"], server)

    def _create_transport(
        self, config: dict
    ) -> Union[StreamableHttpTransport, StdioTransport]:
        """Create the Client object based on the config"""

        transport_type = config.get("transport", "http")

        if transport_type == "http":
            return StreamableHttpTransport(url=config["url"])
        elif transport_type == "stdio":
            return StdioTransport(
                command=config["command"],
                args=config.get("args", []),
                env=config.get("env", {}),
                cwd=config.get("cwd", None),
            )
        else:
            raise ValueError(f"Unknown transport: {transport_type}")

    def add_server(self, name: str, config: dict) -> None:
        """Register a new MCP server dynamically."""
        transport = self._create_transport(config)
        self._servers[name] = Client(transport)
        logging.info(
            f"Registered MCP server '{name}' with transport '{config.get('transport', 'http')}'"
        )

    async def list_tools_all(self) -> list:
        """List tools from all registered servers with namespace prefix."""
        all_tools = []

        # Include default client tools (high control private server)
        async with self._default_client:
            session = self._default_client.session
            tools = await load_mcp_tools(session)
            for tool in tools:
                tool.name = f"personal_{tool.name}"
            all_tools.extend(tools)

        # Include tools from all registered servers (for external servers)
        for name, client in self._servers.items():
            async with client:
                session = client.session
                tools = await load_mcp_tools(session)
                # Prefix each tool name with server name to avoid collision
                for tool in tools:
                    tool.name = f"{name}_{tool.name}"
                all_tools.extend(tools)

        logging.info(f"Total tools loaded from all servers: {len(all_tools)}")
        return all_tools

    async def list_tools_output_by_session(self):
        """
        Helper method to list tools with logging. We return a _client.session object and use load_mcp_tools
        to convert to langchain suitable tool.
        Backward compatible - uses default client only.
        """

        start = time.perf_counter()
        attrs = {"component": "mcp_client", "operation": "list_tools"}
        with _tracer.start_as_current_span("mcp_client.list_tools") as span:
            try:
                # Convert the MCP tool to LangChain StructuredTool
                async with self._default_client:
                    session = self._default_client.session
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
        async with self._default_client:
            await self._default_client.ping()
            logging.info("ping: OK")

            result = await self._default_client.list_tools()
            logging.info(f"list_tools: {result}")

            result = await self._default_client.list_prompts()
            logging.info(f"list_prompts: {result}")

            result = await self._default_client.list_resources()
            logging.info(f"list_resources: {result}")

    def _strip_server_prefix(self, mcp_name: str, server_name: str) -> str:
        """Strip server prefix from tool name to match actual MCP tool name.

        Example: 'personal_tool_health_check' -> 'tool_health_check' for 'personal' server
        """
        prefix = f"{server_name}_"
        if mcp_name.startswith(prefix):
            return mcp_name[len(prefix) :]
        return mcp_name

    def get_server_from_tool_name(self, tool_name: str) -> tuple[str | None, str]:
        """Extract server name from prefixed tool name.

        Args:
            tool_name: Tool name which may have server prefix (e.g., 'personal_tool_health_check')

        Returns:
            Tuple of (server_name, original_tool_name)
            - server_name: None if no prefix found (default server)
            - original_tool_name: tool name without prefix

        Example: 'personal_tool_health_check' -> ('personal', 'tool_health_check')
                 'smart-tree_quick_tree' -> ('smart-tree', 'quick_tree')
                 'unknown_tool' -> (None, 'unknown_tool')
        """
        # Check registered servers first
        for server_name in self._servers.keys():
            prefix = f"{server_name}_"
            if tool_name.startswith(prefix):
                return (server_name, tool_name[len(prefix) :])

        # No prefix found - use default server
        return (None, tool_name)

    # tool, resource, prompt method use from fastapi gateway to orchestrator
    async def run_client(
        self,
        trace_id: str,
        mcp_name: str,
        call_type: Union["tool", "resource", "prompt"],
        arguments: Optional[dict] = None,
        server_name: Optional[str] = None,
    ):
        """Execute a tool via MCP call_tool.

        Args:
            trace_id: Trace identifier for logging.
            mcp_name: Registered MCP tool name (may include server prefix).
            call_type: Type of call (tool, resource, prompt).
            arguments: Tool arguments.
            server_name: Optional server name to route the call.
                        If None, uses default server.
        """
        # Select client: server_name if provided and exists, else default
        if server_name and server_name in self._servers:
            client = self._servers[server_name]
            actual_server = server_name
            # Strip prefix from tool name to match actual MCP tool name (dupicated maybe removed in the future)
            name = self._strip_server_prefix(mcp_name, actual_server)
        else:
            client = self._default_client
            actual_server = server_name or "default"
            # For default server, strip 'personal_' prefix if present (dupicated maybe removed in the future)
            name = self._strip_server_prefix(mcp_name, "personal")
            # If no prefix was stripped, use original name
            if name == mcp_name:
                name = mcp_name

        # -- Trace block start -- #
        attrs = {
            "mcp.name": mcp_name,
            "mcp.call_type": call_type,
            "mcp.server": actual_server,
        }
        meta = build_propagation_meta(trace_id)
        start = time.perf_counter()

        with _tracer.start_as_current_span("mcp_client.run_client") as span:
            set_span_correlation(span, trace_id)
            span.set_attribute("mcp.name", mcp_name)
            span.set_attribute("mcp.call_type", call_type)
            span.set_attribute("mcp.server", actual_server)
            span.add_event("mcp.call.started")

            # -- Trace block end -- #

            try:
                if call_type == "tool":
                    async with client:
                        try:
                            result = await client.call_tool(
                                name,
                                arguments,
                                timeout=5000,
                                meta=meta,
                            )

                            # -- Trace block start -- #
                            _mcp_calls_total.add(1, attributes=attrs)
                            span.add_event("mcp.call.succeeded")
                            logging.info(f"[{trace_id}] run_tool/{mcp_name}: {result}")
                            return {
                                "trace_id": trace_id,
                                "result": result,
                            }
                            # -- Trace block end -- #

                        except Exception as e:
                            _mcp_errors_total.add(1, attributes=attrs)
                            span.set_status(Status(StatusCode.ERROR))
                            span.add_event("mcp.call.failed")
                            logging.error(
                                f"[{trace_id}] run_tool/tool/{mcp_name} failed: {e}"
                            )
                            raise

                if call_type == "resource":
                    async with client:
                        try:
                            result = await client.read_resource(
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
                    async with client:
                        try:
                            result = await client.get_prompt(
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


# if __name__ == "__main__":
#     # Test code to run the MCP client and execute a tool call
#     # NOTE: Update the path below to point to your actual external MCP server

#     # Example: Test with MCP-Server-Playwright
#     client_obj = StreamableHttpTransport(
#         url="https://mcp.tavily.com/mcp/?tavilyApiKey=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"
#     )

#     async def test():
#         # Using a single context block for both list_tools and call_tool
#         async with Client(client_obj) as client:
#             # List available tools
#             output = await client.list_tools()
#             print(f"Tools available: {len(output)}")

#             # # Example: Call a tool
#             result = await client.call_tool(
#                 "tavily_search",
#                 {"query": "https://google.com"},
#                 timeout=30,
#             )
#             print("Result:", result)

#     asyncio.run(test())
