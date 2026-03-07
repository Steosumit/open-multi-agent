# Plan: Wire `tool_node` to `MCPClient.run_tool` in `orchestrator.py`

Replace the dead `tools_by_name` lookup in `tool_node` with async `MCPClient.run_tool` calls, making `tool_node` async-native to work correctly inside FastAPI's running event loop, and fix all broken imports/paths along the way.

## Steps

1. **Fix `pyproject.toml`** ✅ — add `[tool.hatch.build.targets.wheel] packages = ["app", "mcp"]` so both are importable as top-level packages from the project root.

2. **Fix `SYSTEM_PROMPT` path in `app/orchestrator.py`** ✅ — replaced hardcoded `"/core/SYSTEM.md"` with `pathlib.Path(__file__).parent.parent / "core" / "SYSTEM.md"`.

3. **Import `MCPClient` and `SERVER_URL` in `app/orchestrator.py`** ✅ — `from mcp.client import MCPClient` and `from mcp.config import SERVER_URL`.

4. **Instantiate `mcp_client` at module level in `app/orchestrator.py`** ✅ — `mcp_client = MCPClient(base_url=SERVER_URL)` singleton, mirrors `_mcp_client` in `main.py`.

5. **Rewrite `tool_node` as `async def` in `app/orchestrator.py`** ✅ — iterates `state["messages"][-1].tool_calls` (`.tool_calls` items have `"name"`, `"args"`, `"id"` keys — confirmed valid LangChain `ToolCall` keys), calls `await mcp_client.run_tool(trace_id, tool_call["name"], tool_call["args"])`, extracts result via `response["result"].content[0].text`, wraps in `ToolMessage`. Per-call `try/except` logs `trace_id` + tool name and appends an error `ToolMessage` on failure. **No `asyncio.run`** — FastAPI/uvicorn already owns the event loop.

6. **Update graph invocation in `app/main.py`** — when the LangGraph graph is wired into the FastAPI route, use `await graph.ainvoke(...)` instead of `graph.invoke(...)`. The route is already `async def` so this is straightforward.

7. **Remove dead imports/symbols** ✅ — deleted `tools_by_name`, re-imported `ToolMessage` from `langchain_core.messages`, cleaned up `langchain.messages` import.

---

## Further Considerations

1. **`asyncio.run` is not viable** — orchestrator is called from an async FastAPI route inside uvicorn's event loop. `tool_node` is now `async def`; use `await graph.ainvoke(...)` end-to-end. LangGraph natively supports async nodes.

2. **Per-call HTTP session in `run_tool`** — each `async with self._client` opens/closes a session per tool call. Fine for now; future optimisation would use a persistent session / connection pool.

3. **`result["result"]` is a `fastmcp` `CallToolResult`** ✅ — text extracted via `response["result"].content[0].text` and cast to `str` before passing to `ToolMessage.content`.
