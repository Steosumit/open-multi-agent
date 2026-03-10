# mcp_local/__init__.py
from mcp_local.client import MCPClient
from mcp_local.config import SERVER_URL, SERVER_PORT
from mcp_local.server import mcp

__all__ = ["MCPClient", "SERVER_URL", "SERVER_PORT", "mcp"]
