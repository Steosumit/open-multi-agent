from opentelemetry import trace

from observability.otel import build_propagation_meta, extract_parent_context


def test_build_propagation_meta_includes_app_trace_id():
    meta = build_propagation_meta("trace-abc-123")
    assert meta["app.trace_id"] == "trace-abc-123"


def test_extract_parent_context_reads_traceparent():
    meta = {
        "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
    }
    parent_ctx = extract_parent_context(meta)
    span_context = trace.get_current_span(parent_ctx).get_span_context()
    assert span_context.is_valid
    assert format(span_context.trace_id, "032x") == "4bf92f3577b34da6a3ce929d0e0e4736"
