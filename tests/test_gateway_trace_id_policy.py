import re

from app.main import _is_valid_trace_id
from app.main import _choose_trace_id


def test_is_valid_trace_id_accepts_expected_values():
    assert _is_valid_trace_id("abc12345")
    assert _is_valid_trace_id("trace_id-XYZ_123")
    assert _is_valid_trace_id("a" * 64)


def test_is_valid_trace_id_rejects_invalid_values():
    assert not _is_valid_trace_id(None)
    assert not _is_valid_trace_id("")
    assert not _is_valid_trace_id("abc")
    assert not _is_valid_trace_id("bad trace id")
    assert not _is_valid_trace_id("a" * 65)


def test_generated_uuid_hex_matches_expected_shape():
    import uuid

    generated = uuid.uuid4().hex
    assert len(generated) == 32
    assert re.fullmatch(r"[0-9a-f]{32}", generated)


def test_choose_trace_id_prefers_valid_candidate():
    assert _choose_trace_id("valid-trace-12345") == "valid-trace-12345"


def test_choose_trace_id_generates_for_invalid_candidate():
    chosen = _choose_trace_id("bad trace id")
    assert chosen != "bad trace id"
    assert len(chosen) == 32
    assert re.fullmatch(r"[0-9a-f]{32}", chosen)
