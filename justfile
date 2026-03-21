# justfile

# Set the default shell for windows(COMMENT THIS IN LINUX)
set shell := ["powershell.exe", "-c"]

# Set the default run action, show the possible command list (@ to hidden the intentional command in output)
default:
    @just --list


# Main Commands

# Run all from the orchestrator (agent test)
run-orchestrator: mcp redis-dev orchestrator

# Run all from the gateway (full test)
run-gateway: mcp redis-dev gateway


# Start Redis Docker container

# Start Redis in detached mode
redis-dev:
    docker run --name redis-short-term -p 6379:6379 redis:latest

# Start Redis in detached mode
redis:
    docker run -d --name redis-short-term -p 6379:6379 redis:latest

# Kill the redis container
redis-clean:
    docker stop redis-short-term
    docker rm redis-short-term


# Run the MCP Server
mcp:
    python -m mcp_local.server


# Run the orchestrator
orchestrator:
    python -m app.orchestrator


# Run the FastAPI Gateway
gateway:
    uvicorn app.main:app --reload
