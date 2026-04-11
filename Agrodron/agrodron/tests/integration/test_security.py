"""Integration tests: security monitor policy enforcement."""
import json

from agrodron.tests.integration.integration_bus import IntegrationBus
from sdk.topic_utils import topic_for

from components.security_monitor.src.security_monitor import SecurityMonitorComponent


def test_isolation_replaces_policies():
    bus = IntegrationBus()

    sm = SecurityMonitorComponent(
        component_id="security_monitor",
        bus=bus,
        security_policies=json.dumps([
            {"sender": topic_for("autopilot"), "topic": topic_for("motors"), "action": "set_target"},
        ]),
    )

    assert len(sm._policies) == 1

    msg = {
        "action": "isolation_start",
        "sender": topic_for("emergensy"),
        "payload": {"reason": "TEST"},
    }
    result = sm._handle_isolation_start(msg)
    assert result is not None
    assert result.get("activated") is True
    assert sm._mode == "ISOLATED"

    assert (topic_for("emergensy"), topic_for("motors"), "land") in sm._policies
    assert (topic_for("emergensy"), topic_for("sprayer"), "set_spray") in sm._policies
    assert (topic_for("autopilot"), topic_for("motors"), "set_target") not in sm._policies


def test_policy_management():
    bus = IntegrationBus()

    sm = SecurityMonitorComponent(
        component_id="security_monitor",
        bus=bus,
        security_policies="[]",
        policy_admin_sender="admin",
    )

    assert len(sm._policies) == 0

    set_msg = {
        "action": "set_policy",
        "sender": "admin",
        "payload": {"sender": "x", "topic": "y", "action": "z"},
    }
    result = sm._handle_set_policy(set_msg)
    assert result["updated"] is True
    assert ("x", "y", "z") in sm._policies

    remove_msg = {
        "action": "remove_policy",
        "sender": "admin",
        "payload": {"sender": "x", "topic": "y", "action": "z"},
    }
    result = sm._handle_remove_policy(remove_msg)
    assert result["removed"] is True
    assert ("x", "y", "z") not in sm._policies


def test_policy_management_forbidden_for_non_admin():
    bus = IntegrationBus()

    sm = SecurityMonitorComponent(
        component_id="security_monitor",
        bus=bus,
        security_policies="[]",
        policy_admin_sender="admin",
    )

    msg = {
        "action": "set_policy",
        "sender": "hacker",
        "payload": {"sender": "x", "topic": "y", "action": "z"},
    }
    result = sm._handle_set_policy(msg)
    assert result["updated"] is False
    assert result["error"] == "forbidden"
