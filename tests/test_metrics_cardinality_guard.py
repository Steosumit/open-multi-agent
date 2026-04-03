from app.main import _gateway_metric_attributes


def test_gateway_metric_attributes_are_low_cardinality():
    attrs = _gateway_metric_attributes()
    assert "app.trace_id" not in attrs
    assert attrs == {"gateway.endpoint": "/agent-task"}
