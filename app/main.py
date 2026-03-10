import uuid
from fastapi import FastAPI
from app.models import AgentTaskRequest, AgentTaskResponse
from app.orchestrator import run_agent


app = FastAPI()

@app.post("/agent-task", response_model=AgentTaskResponse)
async def agent_task(agent_task_request: AgentTaskRequest) -> AgentTaskResponse:
    """Handle agent task requests by routing through the LangGraph orchestrator."""

    trace_id = uuid.uuid4().hex

    orchestrator_result = await run_agent(
        message=agent_task_request.message,
        trace_id=trace_id,
    )

    # DEBUG TEST: display the output of orchestrator in the console
    print("-" * 20, "Orchestrator Output", "-" * 20)
    print(f"Orchestrator result for trace_id {trace_id}: {orchestrator_result}")
    print("-" * 20, "Orchestrator Output", "-" * 20)

    # This result is connected to openclaw
    return AgentTaskResponse(
        trace_id=trace_id,
        result=orchestrator_result,
    )



