import re
import time
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.trace import Status, StatusCode

from app.models import AgentTaskRequest, AgentTaskResponse
from observability import (
    clear_current_trace_id,
    get_meter,
    get_tracer,
    init_observability,
    instrument_fastapi_app,
    set_current_trace_id,
    set_span_correlation,
)

app = FastAPI()

# CORS
# It makes sure what origins are allowed to access the gateway secondarily
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],  # Front origin
    allow_credentials=True,
    allow_methods=["*"],                      # Allow all methods (POST, GET, etc)
    allow_headers=["*"],                      # Allow all headers
)

init_observability(service_name="fastapi-gateway")
instrument_fastapi_app(app)

_tracer = get_tracer(__name__)
_meter = get_meter(__name__)

_request_counter = _meter.create_counter(
    name="gateway_requests_total",
    description="Total gateway requests",
)
_error_counter = _meter.create_counter(
    name="gateway_request_errors_total",
    description="Total gateway request failures",
)
_latency_histogram = _meter.create_histogram(
    name="gateway_request_latency_ms",
    description="Gateway request latency in ms",
    unit="ms",
)

_TRACE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _is_valid_trace_id(value: str | None) -> bool:
    if value is None:
        return False
    return _TRACE_ID_PATTERN.fullmatch(value.strip()) is not None


def _choose_trace_id(candidate_trace_id: str | None) -> str:
    candidate = (candidate_trace_id or "").strip()
    if _is_valid_trace_id(candidate):
        return candidate
    return uuid.uuid4().hex


def _gateway_metric_attributes() -> dict[str, str]:
    return {
        "gateway.endpoint": "/agent-task",
    }


def _get_run_agent():
    from app.orchestrator import run_agent

    return run_agent


@app.post("/agent-task", response_model=AgentTaskResponse)
async def agent_task(agent_task_request: AgentTaskRequest) -> AgentTaskResponse:
    """Handle agent task requests by routing through the LangGraph orchestrator."""

    trace_id = _choose_trace_id(agent_task_request.trace_id)

    attributes = _gateway_metric_attributes()
    _request_counter.add(1, attributes=attributes)
    start = time.perf_counter()

    set_current_trace_id(trace_id)
    try:
        with _tracer.start_as_current_span("gateway.agent_task") as span:
            set_span_correlation(span, trace_id)
            span.add_event("agent.request.received")

            run_agent = _get_run_agent()
            orchestrator_result = await run_agent(
                message=agent_task_request.message,
                trace_id=trace_id,
            )

            span.add_event("agent.request.completed")
            return AgentTaskResponse(
                trace_id=trace_id,
                result=orchestrator_result,
            )
    except Exception:
        _error_counter.add(1, attributes=attributes)
        with _tracer.start_as_current_span("gateway.agent_task.error") as span:
            set_span_correlation(span, trace_id)
            span.set_status(Status(StatusCode.ERROR))
            span.add_event("agent.request.failed")
        raise
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        _latency_histogram.record(elapsed_ms, attributes=attributes)
        clear_current_trace_id()
