# Setup

## TIP
> Install `just` to setup

## Redis Server: Short Term Memory

If you do not have redis docker image, pull it.

Create and start the redis server used for short term memory:

```powershell
docker run -d --name redis-short-term -p 6379:6379 redis:latest
```

## Running

Start the MCP server:

```powershell
python -m mcp_local.server
```

Start the FastAPI gateway:

```powershell
uvicorn app.main:app --reload
```

## External MCP Servers Supported (Tested)

- MCP-Server-Playwright:
https://glama.ai/mcp/servers/VikashLoomba/MCP-Server-Playwright

- 

