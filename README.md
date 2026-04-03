# open-multi-agent

A modular, production-ready multi-agent orchestration framework built on LangGraph, FastAPI, and Model Context Protocol (MCP).

## Overview

`open-multi-agent` provides a scalable platform for building AI agents with:
- **LangGraph orchestration** for complex agent workflows
- **FastAPI gateway** for HTTP-based agent access
- **MCP Local integration** for modular tool management
- **Redis-based short-term memory** with persistent long-term storage via ChromaDB
- **Full observability** with OpenTelemetry tracing

## Key Features

### 🔗 OpenClaw Integration and Security
Seamless integration with [OpenClaw](https://openclaw.ai/) for A2A multi agent workflows. Only core agent is exposed to private MCP servers, enabling powerful automation capabilities keeping the robustness of OpenClaw in a highly secure manner

### 🧩 Modular Control
**MCP Local Server** provides a decoupled architecture:
- Define tools and prompts independently of the main agent
- Flexibility in tool additions or upgrades
- Namespace-based tool organization

### 🧠 Memory Management
- **Short-term**: Redis-backed conversation history with checkpoint recovery
- **Long-term**: ChromaDB vector embeddings for semantic search
- Automatic pruning and summarization of old conversations

### 📊 Observability
Built-in OpenTelemetry instrumentation:
- Distributed tracing across FastAPI, HTTPX, and custom spans
- OTLP exporter for Jaeger/Datadog integration
- Request-level context propagation
- Performance metrics and error tracking

### 🔒 Security (Planned)
*Next iterations will include:*
- Input validation and rate limiting
- API authentication (JWT/OAuth2)
- Tool execution sandboxing
- Audit logging

## Quick Start

### Prerequisites
- Python 3.13+
- Docker (for Redis & ChromaDB)
- Google Generative AI API key

### Setup

1. **Clone and install dependencies**
   ```bash
   git clone https://github.com/steosumit/open-multi-agent
   cd open-multi-agent
   uv sync
   ```

2. **Set environment variables**
   ```bash
   cp .env.example .env
   # Add your GOOGLE_API_KEY and other configs
   ```

3. **Start infrastructure** (using justfile)
   ```bash
   just dev  # Starts Redis, MCP Server, and FastAPI Gateway
   ```

   Or manually:
   ```powershell
   docker run -d --name redis-short-term -p 6379:6379 redis:latest
   python -m mcp_local.server
   uvicorn app.main:app --reload --port 8001
   ```

4. **Test the agent**
   ```powershell
   $body = @{
       message = "What can you do?"
       trace_id = "test-001"
   } | ConvertTo-Json
   
   Invoke-WebRequest -Uri "http://localhost:8001/agent-task" `
       -Method POST `
       -ContentType "application/json" `
       -Body $body
   ```

## Truncated Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Gateway (8001)                  │
│                    (HTTP API Interface)                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    LangGraph Orchestrator                    │
│         (llm_node → tool_node → summarization_node)          │
└──────┬───────────────────────┬──────────────────────┬───────┘
       │                       │                      │
   ┌───▼────┐         ┌────────▼────┐       ┌────────▼────┐
   │  MCP    │         │   Memory    │       │    Tracing  │
   │ Server  │         │  (Redis +   │       │ (OpenTel)   │
   │ (8000)  │         │ ChromaDB)   │       │   (OTLP)    │
   └─────────┘         └─────────────┘       └─────────────┘
```

## Project Structure

```
open-multi-agent/
├── app/                 # FastAPI gateway and routes
├── core/                # Configuration and utilities
├── mcp_local/           # MCP server implementation
├── memory/              # Short-term (Redis) and long-term (ChromaDB) storage
├── observability/       # OpenTelemetry setup
├── ops/                 # Deployment and operations
├── justfile             # Task automation
└── pyproject.toml       # Project dependencies
```

## Development

### Run Tests
```bash
pytest tests/ -v
```

### Format Code
```bash
ruff format .
```

### View API Documentation
Navigate to `http://localhost:8001/docs` for interactive Swagger UI.

## Next Steps

- [x] Core agent orchestration
- [x] MCP Local integration
- [x] Redis short-term memory
- [x] ChromaDB long-term memory
- [x] OpenTelemetry observability
- [ ] Authentication & rate limiting
- [ ] Tool execution sandboxing
- [ ] Multi-agent collaboration

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m "Add feature"`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

## License

MIT

## Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/instrumentation/python/)

*Made with ❤️ by [steosumit](https://linkedin.com/in/steosumit) for the open-source community.*
