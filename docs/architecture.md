# Overview

This document outlines the directory structure and the use of each of the
modules we have in our project


# Directory Structure

```

personal_agent/
│
├── app/
│   ├── main.py                # FastAPI Gateway entry
│   ├── routes.py              # A2A endpoints
│   └── orchestrator.py        # LangGraph setup
│
├── mcp/
│   ├── client.py              # MCP Client (HTTP wrapper)
│   ├── server.py              # MCP FastAPI execution service
│   ├── schemas.py             # Pydantic request/response models
│   ├── registry.py            # Tool registry
│   ├── adapters.py            # LLM + tool adapters
│   └── config.py              # MCP configuration
│
├── memory/
│   ├── short_term.py          # Graph state helpers
│   └── long_term.py           # SQLite + embeddings
│
├── observability/
│   └── logger.py              # Structured logging
│
└── requirements.txt

```


# Process

*5-Day Execution Plan*

## Task 1 — MCP Server (Execution Engine)
- Build FastAPI MCP server
- Implement `/health` and `/tool/execute`
- Add basic tool registry
- Mock one working tool (e.g., `usage_analyzer`)
- Verify server runs independently

---

## Task 2 — MCP Client (Execution Boundary)
- Implement `mcp/client.py`
- Add structured payload builder
- Inject `trace_id`
- Add timeout + error handling
- Test client → server communication

---

## Task 3 — FastAPI Gateway (A2A Layer)
- Create `/agent-task` endpoint
- Add schema validation
- Generate `trace_id`
- Call MCP client directly
- Validate full HTTP chain (OpenClaw → Gateway → MCP → Response)

---

## Task 4 — LangGraph Orchestrator
- Define state structure
- Implement minimal nodes:
  - Intent classifier
  - Tool decision
  - Tool execution
  - Response formatter
- Replace direct MCP call with orchestrated flow


---

## Task 5 — Memory, Observability, Security

### Memory
- Add Redis logging (short term memory)
  - Implement the redis backend in short_term.py
    - yield a redis checkpointer connected to a redis server
    - integrate the checkpointer in the orchestrator.py

- Add Vector DB(chromaDB) logging (long-term memory)

The "Episodic Memory" Approach:
  
  1.  Trigger: When short-term memory (Redis) hits a threshold (e.g., 20 messages).
  
  2.  Action:
      *   Send the last 20 messages to an LLM and summarize it using the summary_prompt
      *   Store: Save this summary + metadata (timestamp) into a Vector Database (e.g., chromadb locally or pinecone cloud).
  3.  Retrieval:
      *   On every new user message, embed the query.
      *   Search the Vector DB for the top 3 most relevant past summaries.
      *   Inject these summaries into the system prompt context: "Relevant Past Context: {summary1}, {summary2}, {summary3}".

### Observability
MELT: Metrics, Events, Logs, Traces for fastAPI gateway, mcp server, orchestrator with `trace_id` correlation across all components.

#### Collector + Exporters (OTel + Jaeger)
- A local OTel Collector receives OTLP from gateway, orchestrator, and MCP server.
- Collector exports traces to Jaeger and metrics to a Prometheus scrape endpoint.
- Files:
  - `ops/otel-collector.yaml`
  - `ops/docker-compose.observability.yml`
- Run:
  - `just obs-up` (starts collector + jaeger)
  - `just obs-ps` (status)
  - `just obs-down` (stop stack)
- Endpoints:
  - Jaeger UI: `http://localhost:16686`
  - Collector OTLP gRPC receiver: `http://localhost:4317`
  - Collector OTLP HTTP receiver: `http://localhost:4318`
  - Collector Prometheus metrics exporter: `http://localhost:9464/metrics`

#### Step 3: Runtime environment inputs
- `OTEL_EXPORTER_OTLP_ENDPOINT`
  - Default: `http://localhost:4317`
  - Used by all instrumented services as OTLP export target.
- `OTEL_DEPLOYMENT_ENV`
  - Default: `dev`
  - Added to telemetry resource attribute `deployment.environment`.

- Hybride Code + Auto Instrumentation:
Given your MELT requirement and explicit trace_id correlation across gateway/orchestrator/MCP, I’m proposing a hybrid but code-first approach:
- Code-based for business spans/events/metrics and guaranteed app.trace_id propagation.
- Auto-instrumentation only for framework/client plumbing (FastAPI/httpx) to reduce boilerplate.

Gateway + Orchestrator + MCP (Instrumentation)-> OTLP Receiver (Collector) -> Processors -> Jaeger (traces)  
                                           \-> Prometheus (metrics)  
                                           \-> Log backend (optional)


### Security
- Add tool whitelist enforcement
- Add input validation and basic sanitization

## Future: Add Self Tool Creation Ability

The agent should be able to create tools and skills for itself and be ready according to the user. Presently we manually add the tools, resources, and prompt codes
through the MCP server

---

## Outcome
- A2A communication working[DONE]
- Structured tool orchestration [DONE]
- MCP execution boundary [DONE]
- Persistent memory[DONE]
- Long term memory[DONE]
- Observability logging
- Basic security controls
- Clean, extensible architecture
