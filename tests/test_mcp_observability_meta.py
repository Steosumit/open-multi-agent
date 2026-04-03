from types import SimpleNamespace

from mcp_local.server import _extract_app_trace_id, _extract_meta


class _FakeContext:
    def __init__(self, meta: dict | None = None, arguments: dict | None = None):
        params = SimpleNamespace(meta=meta, arguments=arguments)
        request = SimpleNamespace(params=params)
        self.request_context = SimpleNamespace(request=request)


def test_extract_meta_returns_meta_dict():
    ctx = _FakeContext(meta={"traceparent": "abc", "app.trace_id": "t1"})
    result = _extract_meta(ctx)
    assert result["traceparent"] == "abc"
    assert result["app.trace_id"] == "t1"


def test_extract_app_trace_id_prefers_meta_value():
    ctx = _FakeContext(
        meta={"app.trace_id": "meta-trace"},
        arguments={"trace_id": "arg-trace"},
    )
    assert _extract_app_trace_id(ctx) == "meta-trace"


def test_extract_app_trace_id_falls_back_to_arguments():
    ctx = _FakeContext(meta={}, arguments={"trace_id": "arg-trace"})
    assert _extract_app_trace_id(ctx) == "arg-trace"
