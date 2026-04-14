from fastmcp.client.transports import StreamableHttpTransport, StdioTransport
from fastmcp import Client
import asyncio

if __name__ == "__main__":
    # Test code to run the MCP client and execute a tool call
    # NOTE: Update the path below to point to your actual external MCP server

    # Example: Test with MCP-Server-Playwright
    client_obj = StreamableHttpTransport(
        url="https://mcp.tavily.com/mcp/?tavilyApiKey=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"
    )

    async def test():
        # Using a single context block for both list_tools and call_tool
        async with Client(client_obj) as client:
            # List available tools
            output = await client.list_tools()
            print(f"Tools available: {len(output)}")

            # # Example: Call a tool
            result = await client.call_tool(
                "tavily_crawl",
                {"query": "https://google.com"},
                timeout=30,
            )
            print("Result:", result)

    asyncio.run(test())
