# open-multi-agent

A modular, production-ready multi-agent orchestration framework built on LangGraph, FastAPI, and Model Context Protocol (MCP). Seamlessly orchestrate complex AI agent workflows with built-in memory management, observability, and secure integration capabilities.

## Technologies

- **LangGraph** - Agent orchestration and workflow management
- **FastAPI** - High-performance HTTP API gateway
- **Model Context Protocol (MCP)** - Modular tool and prompt management
- **Redis** - Short-term memory and checkpoint recovery
- **ChromaDB** - Long-term semantic memory with vector embeddings
- **OpenTelemetry** - Distributed tracing and observability
- **Google Generative AI** - LLM integration
- **Python 3.13+** - Modern async/await support
- **Docker** - Containerized infrastructure

## Features

### OpenClaw Integration and Security
Seamless integration with [OpenClaw](https://openclaw.ai/) for A2A multi agent workflows. Only core agent is exposed to private MCP servers, enabling powerful automation capabilities keeping the robustness of OpenClaw in a highly secure manner

### Modular Control
**MCP Local Server** provides a decoupled architecture:
- Define tools and prompts independently of the main agent
- Flexibility in tool additions or upgrades
- Namespace-based tool organization

### Memory Management
- **Short-term**: Redis-backed conversation history with checkpoint recovery
- **Long-term**: ChromaDB vector embeddings for semantic search
- Automatic pruning and summarization of old conversations

### Observability
Built-in OpenTelemetry instrumentation:
- Distributed tracing across FastAPI, HTTPX, and custom spans
- OTLP exporter for Jaeger/Datadog integration
- Request-level context propagation
- Performance metrics and error tracking

### Security (Planned)
- Tool Access Control
- Argument Sanitization

*Next iterations will include:*
- API authentication (JWT/OAuth2)
- Tool execution sandboxing

## The Process
I used OpenClaw and was amazed to see the capabilities and control it had on the user's PC, but I was more aroused by seeing the security it lacked. If I have authenticated and connected OpenClaw to my telegram, a simple, "delete file.txt" would run without any restrictions. It led me to think about a agent framework from sratch that would connect to OpenClaw for its robust capabilities and at the same time keep the private functionalities under control of the private agent.
### The Journey
I started with making a minimalistic architecture and a working setup of the gateway, mcp server and client, opentelemetry, and basic security controls. Then I realized a few short comings that I documented in the file `docs/Learnings.md`.

The top mistakes and learnings:
- Agnostic MCP Client: I had made the client hardcodedly connected to my own mcp server, and I found it impossible to connect to open source servers. I ended up making MCPRegistry class and distilled the MCPClient class to HTTP streams and Stdio initialization, and added a config file
- Memory management: the importance of reducer and summarization of messages before sending it to the llm
- Docker Compose Setup: learned to create justfile to handle too many ports and docker engine workings

for more read `docs/Learnings.md`.

### The Plan
In the future I will be applying LLM Top 10 best practices to make the agent more secure. Keep checking in the future :)

## Quick Start

### Prerequisites
- Python 3.13+
- Docker (for Redis & ChromaDB)
- Google Generative AI API key

### Installation & Setup

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

## Architecture

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
├── pyproject.toml       # Project dependencies
└── README.md            # This file
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

---

*Made with ❤️ by [steosumit](https://linkedin.com/in/steosumit) for the open-source community.*
