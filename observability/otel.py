"""OpenTelemetry bootstrap and correlation helpers.

Instrumentation:
- Code-based spans/events/metrics
- FastAPI/httpx auto instrumentation
- app.trace_id correlation helpers
"""

from __future__ import annotations

import contextvars
import logging
from collections.abc import Mapping

from opentelemetry.context import Context
from opentelemetry import metrics, trace
from opentelemetry.propagate import extract, inject
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span

from core.config import OTEL_DEPLOYMENT_ENV, OTEL_EXPORTER_OTLP_ENDPOINT


_trace_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "app_trace_id", default=None
)

_initialized: bool = False


def init_observability(service_name: str, service_version: str = "0.1.0") -> None:
    """Initialize tracing + metrics providers exactly once per process."""
    global _initialized
    if _initialized:
        return

    otlp_endpoint = OTEL_EXPORTER_OTLP_ENDPOINT
    deployment_env = OTEL_DEPLOYMENT_ENV

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": service_version,
            "deployment.environment": deployment_env,
        }
    )

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))
    )
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True)
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    _initialized = True
    logging.info("Observability initialized for service=%s", service_name)


def instrument_fastapi_app(app) -> None:
    """Apply FastAPI auto-instrumentation once."""
    FastAPIInstrumentor.instrument_app(app)


def instrument_httpx_client() -> None:
    """Apply httpx auto-instrumentation once."""
    HTTPXClientInstrumentor().instrument()


def get_tracer(name: str):
    return trace.get_tracer(name)


def get_meter(name: str):
    return metrics.get_meter(name)


def set_current_trace_id(app_trace_id: str) -> None:
    _trace_id_ctx.set(app_trace_id)


def get_current_trace_id() -> str | None:
    return _trace_id_ctx.get()


def clear_current_trace_id() -> None:
    _trace_id_ctx.set(None)


def set_span_correlation(span: Span, app_trace_id: str | None) -> None:
    """Attach business correlation id to span attributes/events."""
    if app_trace_id:
        span.set_attribute("app.trace_id", app_trace_id)


def build_propagation_meta(app_trace_id: str | None) -> dict[str, str]:
    """Build MCP meta carrier with W3C trace propagation fields."""
    carrier: dict[str, str] = {}
    if app_trace_id:
        carrier["app.trace_id"] = app_trace_id
    inject(carrier=carrier)
    return carrier


def extract_parent_context(meta: Mapping[str, object] | None) -> Context:
    """Extract parent context from incoming MCP meta carrier."""
    carrier: dict[str, str] = {}
    if meta:
        for key, value in meta.items():
            if value is None:
                continue
            carrier[str(key)] = str(value)
    return extract(carrier=carrier)
