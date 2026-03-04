import asyncio
from fastmcp import Client
from config import SERVER_URL
import logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s\n-\n%(message)s",
)


class MCPClient:
    """MCP tool runner using fastmcp async client."""

    def __init__(self, base_url: str) -> None:
        self._client = Client(base_url)

    @staticmethod
    def _build_tool_payload(trace_id: str, tool_name: str, arguments: dict) -> tuple[str, dict]:
        """Build and log tool call payload with tracing.

        Args:
            trace_id: Trace identifier for logging.
            tool_name: Registered MCP tool name.
            arguments: Flexible input arguments.

        Returns:
            Tuple of (tool_name, arguments).
        """

        logging.info(f"[{trace_id}] Building payload for tool: {tool_name}")

        # TODO: Implement tracing logic and history management here later
        return tool_name, arguments

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

    async def run_tool(self, trace_id: str, tool_name: str, arguments: dict) -> dict:
        """Execute a tool via MCP call_tool."""

        name, args = self._build_tool_payload(trace_id, tool_name, arguments)

        async with self._client:
            try:
                result = await self._client.call_tool(name, args, timeout=5)
                logging.info(f"[{trace_id}] run_tool/{tool_name}: {result}")
                return {
                    "trace_id": trace_id,
                    "result": result,
                }
            except Exception as e:
                logging.error(f"[{trace_id}] run_tool/{tool_name} failed: {e}")
                raise


if __name__ == "__main__":

    # Test code to run the MCP client and execute a tool call
    client_obj = MCPClient(base_url=SERVER_URL)

    # We run the async function inside asyncio with handle it in parallel
    output = asyncio.run(
        client_obj.run_tool("trace-123", "tool_health_check", {})
    )
    logging.info(f"Tool execution result: {output}")

