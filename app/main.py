import uuid
from fastapi import FastAPI
from models import AgentTaskRequest, AgentTaskResponse
from mcp.config import SERVER_URL
from mcp.client import MCPClient


app = FastAPI()
_mcp_client = MCPClient(base_url=SERVER_URL)  # created only once


@app.post("/agent-task", response_model=AgentTaskResponse)
async def agent_task(agent_task_request: AgentTaskRequest) -> AgentTaskResponse:

    # Generate a trace_id for logging and tracing purposes
    trace_id = uuid.uuid4().hex

    # Send the request to the MCP client
    response = await _mcp_client.run_tool(
        trace_id=trace_id,
        tool_name=agent_task_request.tool_name,
        arguments=agent_task_request.arguments,
    )

    return AgentTaskResponse(
        trace_id=response["trace_id"],
        result=response["result"],
    )



