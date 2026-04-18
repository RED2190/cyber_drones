"""Integration tests: proxy_request through security_monitor."""
import json

from agrodron.tests.integration.integration_bus import IntegrationBus
from systems.agrodron.sdk.topic_utils import topic_for

from systems.agrodron.src.security_monitor.src.security_monitor import SecurityMonitorComponent
from systems.agrodron.src.motors.src.motors import MotorsComponent


def _policies_json(policies):
    return json.dumps(policies)


def test_proxy_request_motors_get_state():
    bus = IntegrationBus()
    motors_topic = topic_for("motors")
    sm_topic = topic_for("security_monitor")

    motors = MotorsComponent(
        component_id="motors",
        bus=bus,
        topic=motors_topic,
    )

    sm = SecurityMonitorComponent(
        component_id="security_monitor",
        bus=bus,
        security_policies=_policies_json([
            {"sender": topic_for("telemetry"), "topic": motors_topic, "action": "get_state"},
        ]),
    )

    bus.register_component(motors_topic, motors)
    bus.register_component(sm_topic, sm)

    msg = {
        "action": "proxy_request",
        "sender": topic_for("telemetry"),
        "payload": {
            "target": {"topic": motors_topic, "action": "get_state"},
            "data": {},
        },
    }

    result = sm._handle_proxy_request(msg)
    assert result is not None
    assert "target_response" in result
    resp = result["target_response"]
    assert "mode" in resp


def test_proxy_request_denied_by_policy():
    bus = IntegrationBus()
    sm_topic = topic_for("security_monitor")

    sm = SecurityMonitorComponent(
        component_id="security_monitor",
        bus=bus,
        security_policies="[]",
    )

    msg = {
        "action": "proxy_request",
        "sender": "unknown",
        "payload": {
            "target": {"topic": topic_for("motors"), "action": "get_state"},
            "data": {},
        },
    }

    result = sm._handle_proxy_request(msg)
    assert isinstance(result, dict)
    assert result.get("ok") is False
    assert result.get("error") == "policy_denied"
