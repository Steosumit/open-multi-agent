import logging
import os
import pathlib
import time

from fastmcp import Context, FastMCP
from opentelemetry.trace import Status, StatusCode

from mcp_local.config import LOG_FILE_PATH, SERVER_PORT
from observability import (
    extract_parent_context,
    get_meter,
    get_tracer,
    init_observability,
    set_span_correlation,
)
from security.argument_sanitizer import sanitize_args

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s\n-\n%(message)s",
)

init_observability(service_name="mcp-server")

_tracer = get_tracer(__name__)
_meter = get_meter(__name__)

_server_calls_total = _meter.create_counter(
    name="mcp_server_calls_total",
    description="Total MCP server handler calls",
)
_server_errors_total = _meter.create_counter(
    name="mcp_server_errors_total",
    description="Total MCP server handler errors",
)
_server_latency_ms = _meter.create_histogram(
    name="mcp_server_handler_latency_ms",
    description="MCP server handler latency in milliseconds",
    unit="ms",
)


def _extract_app_trace_id(ctx: Context) -> str | None:

    params = None
    if not (ctx.request_context and ctx.request_context.request):
        params = getattr(ctx.request_context.request, "params", None)
        return None

    if params is None:
        return None

    meta = getattr(params, "meta", None)
    if isinstance(meta, dict):
        trace_id = meta.get("app.trace_id")
        if isinstance(trace_id, str) and trace_id.strip():
            return trace_id.strip()

    arguments = getattr(params, "arguments", None)
    if isinstance(arguments, dict):
        trace_id = arguments.get("trace_id")
        if isinstance(trace_id, str) and trace_id.strip():
            return trace_id.strip()

    return None


# Function to extract meta data from the request
def _extract_meta(ctx: Context) -> dict[str, object]:
    """Extract metadata from the request context safely."""
    try:
        if not (ctx.request_context and ctx.request_context.request):
            return {}

        request = ctx.request_context.request
        params = getattr(request, "params", {})

        return params
    except (AttributeError, TypeError):
        # If anything fails, just return empty dict
        return {}


mcp = FastMCP(
    name="Personal",
    instructions="""
        This server provides inner tools for personal use. The following tools are available:
        read_logs: Reads the latest logs from the system.
    """,
)


# TOOLS #
@mcp.tool(name="tool_health_check")
@sanitize_args("tool_health_check")
def tool_health_check(ctx: Context, curr_time: str) -> str:
    """Used to check if the server is running."""
    start = time.perf_counter()
    attrs = {"handler": "tool_health_check", "mcp.call_type": "tool"}
    parent_ctx = extract_parent_context(_extract_meta(ctx))
    with _tracer.start_as_current_span(
        "mcp_server.tool_health_check", context=parent_ctx
    ) as span:
        app_trace_id = _extract_app_trace_id(ctx)
        set_span_correlation(span, app_trace_id)
        _server_calls_total.add(1, attributes=attrs)
        span.add_event("mcp.call.started")
        span.add_event("mcp.call.succeeded")
        _server_latency_ms.record(
            (time.perf_counter() - start) * 1000, attributes=attrs
        )
        return f"Server is healthy and running as of {curr_time}"


# RESOURCES #
@mcp.resource(
    uri="data://logs",
    name="logs",
    description="Provides logs for all the past processes",
    tags={"monitoring", "status", "logs", "personal logs"},
)
def read_logs(ctx: Context) -> str:
    """Read the latest logs from the system."""
    start = time.perf_counter()
    attrs = {"handler": "read_logs", "mcp.call_type": "resource"}

    parent_ctx = extract_parent_context(_extract_meta(ctx))
    with _tracer.start_as_current_span(
        "mcp_server.read_logs", context=parent_ctx
    ) as span:
        app_trace_id = _extract_app_trace_id(ctx)
        set_span_correlation(span, app_trace_id)
        _server_calls_total.add(1, attributes=attrs)
        span.add_event("mcp.call.started")

        logging.info(
            f"Reading logs from: {LOG_FILE_PATH}"
        )  # Debug statement to check the log file path

        try:
            os.makedirs(LOG_FILE_PATH.parent, exist_ok=True)
            if not os.path.exists(LOG_FILE_PATH):
                with open(LOG_FILE_PATH, "w"):
                    pass
                logs = "No logs file found. A new log file has been created."
            else:
                logs = (
                    open(LOG_FILE_PATH, "r").read().splitlines()[-100:]
                )  # Read the last 100 lines of logs
            logging.info(f"read_logs: successfully read logs")
            span.add_event("mcp.call.succeeded")
        except OSError as e:
            _server_errors_total.add(1, attributes=attrs)
            span.set_status(Status(StatusCode.ERROR))
            span.add_event("mcp.call.failed")
            logging.error(f"read_logs: Failed to read logs : {e}")
            logs = [
                "Something went wrong while reading logs. Please check the server logs for more details."
            ]

        _server_latency_ms.record(
            (time.perf_counter() - start) * 1000, attributes=attrs
        )
        return str(logs)


# PROMPTS #
@mcp.prompt(
    name="system_prompt", description="Provide the system prompt with tools on startup"
)
async def system_prompt(ctx: Context) -> str:
    """
    System prompt listing all registered tools dynamically.
    Returns:
        Formatted string of all available tool names and descriptions.
    """

    start = time.perf_counter()
    attrs = {"handler": "system_prompt", "mcp.call_type": "prompt"}
    parent_ctx = extract_parent_context(_extract_meta(ctx))
    with _tracer.start_as_current_span(
        "mcp_server.system_prompt", context=parent_ctx
    ) as span:
        app_trace_id = _extract_app_trace_id(ctx)
        set_span_correlation(span, app_trace_id)
        _server_calls_total.add(1, attributes=attrs)
        span.add_event("mcp.call.started")

        # Prepare the tool list context
        tools = await mcp.list_tools()  # fetch registered tools from FastMCP
        tool_lines = "\n".join(
            f"- {tool.name}: {tool.description or 'No description provided.'}"
            for tool in tools
        )

        # Prepare the final SYSTEM_PROMPT by reading from SYSTEM.md
        _SYSTEM_MD = pathlib.Path(__file__).parent.parent / "core" / "SYSTEM.md"
        with open(_SYSTEM_MD, "r") as f:
            system_prompt_text = f.read()

        span.add_event("mcp.call.succeeded")
        _server_latency_ms.record(
            (time.perf_counter() - start) * 1000, attributes=attrs
        )
        return (
            system_prompt_text
            + "\n\n"
            + f"The following tools are available:\n{tool_lines}"
        )


@mcp.prompt(
    name="summary_prompt",
    description="Provide the prompt to summarize a bunch of messages in memory management",
)
async def summary_prompt(ctx: Context) -> str:
    """
    Prompt for summarizing messages in memory management.
    Returns:
        A string prompt that guides the summarization of messages.
    """
    start = time.perf_counter()
    attrs = {"handler": "summary_prompt", "mcp.call_type": "prompt"}
    parent_ctx = extract_parent_context(_extract_meta(ctx))
    with _tracer.start_as_current_span(
        "mcp_server.summary_prompt", context=parent_ctx
    ) as span:
        app_trace_id = _extract_app_trace_id(ctx)
        set_span_correlation(span, app_trace_id)
        _server_calls_total.add(1, attributes=attrs)
        span.add_event("mcp.call.started")
        span.add_event("mcp.call.succeeded")
        _server_latency_ms.record(
            (time.perf_counter() - start) * 1000, attributes=attrs
        )
        return (
            "You are a helpful assistant that summarizes the following message into very concise summaries. "
            "Focus on extracting key information, main points, and any actionable items. "
            "Provide a clear and concise summary that captures the essence of the messages."
        )


if __name__ == "__main__":
    # HTTP transport
    mcp.run(transport="http", host="0.0.0.0", port=SERVER_PORT)
