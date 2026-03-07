# Plan: FastAPI Gateway → Orchestrator Integration (Option B)

Connect `app/main.py` to the LangGraph orchestrator via a `run_agent` wrapper — gateway knows nothing about LangGraph internals.

## Steps

1. **`app/models.py`** — `AgentTaskRequest` uses `message: str` and `trace_id: str` (both required, no defaults — caller is responsible for generating `trace_id`). `AgentTaskResponse` unchanged (`trace_id: str`, `result: Any`).

2. **`app/orchestrator.py`** — add `run_agent` after `agent = agent_builder.compile()`:
   - Signature: `async def run_agent(message: str, trace_id: str) -> str`
   - Calls `await agent.ainvoke({"messages": [HumanMessage(content=message)], "trace_id": trace_id, "llm_calls": 0})`
   - Returns `str(result["messages"][-1].content)`
   - Add `HumanMessage` to imports from `langchain_core.messages`

3. **`app/main.py`** — remove `MCPClient` and `SERVER_URL` imports; import `run_agent` from `orchestrator`. Route calls `await run_agent(message=request.message, trace_id=request.trace_id)` and returns `AgentTaskResponse(trace_id=request.trace_id, result=result)`.

---

## Further Considerations

1. **`llm_node` is sync** — `model.invoke` blocks the event loop; should be `await model.ainvoke(...)` and `llm_node` made `async def` for true async throughput.

2. **`result["messages"][-1].content` type** — can be a `list` for multimodal models; wrapping with `str(...)` in `run_agent` is a safe defensive cast.

3. **Per-call HTTP session in `run_tool`** — each `async with self._client` opens/closes a session per tool call. Fine for now; future optimisation would use a persistent session / connection pool.
