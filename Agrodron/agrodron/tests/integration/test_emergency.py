"""Integration tests: emergency flow (limiter -> emergensy -> isolation)."""
import json

from agrodron.tests.integration.integration_bus import IntegrationBus
from sdk.topic_utils import topic_for

from components.security_monitor.src.security_monitor import SecurityMonitorComponent
from components.emergensy.src.emergensy import EmergenseyComponent


def _build_policies():
    return json.dumps([
        {"sender": topic_for("limiter"), "topic": topic_for("emergensy"), "action": "limiter_event"},
        {"sender": topic_for("emergensy"), "topic": topic_for("motors"), "action": "land"},
        {"sender": topic_for("emergensy"), "topic": topic_for("sprayer"), "action": "set_spray"},
        {"sender": topic_for("emergensy"), "topic": topic_for("journal"), "action": "log_event"},
        {"sender": topic_for("emergensy"), "topic": topic_for("security_monitor"), "action": "isolation_status"},
    ])


def test_limiter_triggers_emergency_protocol():
    bus = IntegrationBus()

    sm = SecurityMonitorComponent(
        component_id="security_monitor",
        bus=bus,
        security_policies=_build_policies(),
    )

    emergensy = EmergenseyComponent(
        component_id="emergensy",
        bus=bus,
        topic=topic_for("emergensy"),
        security_monitor_topic=topic_for("security_monitor"),
    )

    bus.register_component(topic_for("security_monitor"), sm)
    bus.register_component(topic_for("emergensy"), emergensy)

    event_msg = {
        "action": "proxy_publish",
        "sender": topic_for("limiter"),
        "payload": {
            "target": {"topic": topic_for("emergensy"), "action": "limiter_event"},
            "data": {
                "event": "EMERGENCY_LAND_REQUIRED",
                "mission_id": "m-emerg-01",
                "details": {"distance_from_path_m": 15.0},
            },
        },
    }

    result = sm._handle_proxy_publish(event_msg)
    assert result is not None
    assert result.get("published") is True
    assert emergensy._active is True

    assert sm._mode == "ISOLATED"


def test_emergensy_get_state():
    bus = IntegrationBus()

    emergensy = EmergenseyComponent(
        component_id="emergensy",
        bus=bus,
        topic=topic_for("emergensy"),
    )

    msg = {"action": "get_state", "sender": "any"}
    result = emergensy._handle_get_state(msg)
    assert result["active"] is False
