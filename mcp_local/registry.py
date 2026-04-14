"""MCPRegistry - Manage multiple MCP server clients."""

import logging
from typing import Optional

from mcp_local.client import MCPClient
from mcp_local.config import SERVER_URL

logger = logging.getLogger(__name__)


class MCPRegistry:
    """Registry to manage multiple MCP server clients centrally."""

    def __init__(self, base_url: str = SERVER_URL):
        self._default_client = MCPClient(base_url=base_url)
        self._clients: dict[str, MCPClient] = {}
        self._initialized = False

    def add_server(self, name: str, url: str) -> None:
        """Add a new MCP server to the registry."""
        if name in self._clients:
            logger.warning(f"Server '{name}' already exists, skipping")
            return

        client = MCPClient(base_url=url)
        self._clients[name] = client
        logger.info(f"Added MCP server: {name} -> {url}")

    def get_client(self, server_name: Optional[str] = None) -> MCPClient:
        """Get MCP client for a specific server or default."""
        if server_name is None:
            return self._default_client
        return self._clients.get(server_name, self._default_client)

    async def list_all_tools(self) -> list:
        """Get all tools from default client (backward compatible)."""
        return await self._default_client.list_tools_output_by_session()

    async def list_tools_from_all_servers(self) -> list:
        """Get tools from all registered servers with namespace prefix."""
        return await self._default_client.list_tools_all()

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        trace_id: str,
        arguments: Optional[dict] = None,
    ) -> dict:
        """Route tool call to appropriate server."""
        client = self.get_client(server_name)
        return await client.run_client(
            trace_id=trace_id,
            mcp_name=tool_name,
            call_type="tool",
            arguments=arguments,
            server_name=server_name,
        )

    @property
    def servers(self) -> dict[str, MCPClient]:
        """Get all registered clients."""
        return self._clients

    @property
    def default_client(self) -> MCPClient:
        """Get the default client."""
        return self._default_client
