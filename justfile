# justfile

# Set the default shell for windows(COMMENT THIS IN LINUX)
set shell := ["powershell.exe", "-c"]

# Set the default run action, show the possible command list (@ to hidden the intentional command in output)
default:
    @just --list


# Main Commands

# Run all from the orchestrator (agent test)
run-orchestrator: mcp redis-dev orchestrator

# Start Redis Docker container

# Start Redis (Create if missing, or start existing)
redis-dev:
    -docker run -d --name redis-short-term -p 6379:6379 redis:latest 2> $null
    @docker start redis-short-term
    
# Start Redis in detached mode
redis:
    -docker run --name redis-short-term -p 6379:6379 redis:latest
    docker start redis-short-term
    
# Kill the redis container
redis-clean:
    docker stop redis-short-term
    docker rm redis-short-term

# Start ChromaDB container
chromadb-dev:
    docker run --name chroma-server -p 8000:8000 chromadb/chroma
    docker start chroma-server

# Kill the redis container
chromadb-clean:
    docker stop chroma-server
    docker rm chroma-server


# Run the MCP Server
mcp:
    python -m mcp_local.server


# Run the orchestrator
orchestrator:
    python -m app.orchestrator


# Run the FastAPI Gateway
gateway:
    uvicorn app.main:app --port 8001 --reload

# Start OpenTelemetry Collector + Jaeger
obs-up:
    docker compose -f ops/docker-compose.observability.yml up

# Stop OpenTelemetry Collector + Jaeger
obs-down:
    docker compose -f ops/docker-compose.observability.yml down

# Show observability stack status
obs-ps:
    docker compose -f ops/docker-compose.observability.yml ps
