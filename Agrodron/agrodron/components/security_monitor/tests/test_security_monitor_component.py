"""Unit-тесты компонента security_monitor."""
import asyncio
import json

from broker.system_bus import SystemBus
from components.security_monitor import config
from components.security_monitor.src.security_monitor import SecurityMonitorComponent
from sdk.topic_utils import topic_for, topic_prefix

AUTOPILOT_TOPIC = topic_for("autopilot")
NAVIGATION_TOPIC = topic_for("navigation")
MOTORS_TOPIC = topic_for("motors")
JOURNAL_TOPIC = topic_for("journal")
SYSTEM_MONITOR_TOPIC = topic_for("system_monitor")


class DummyBus(SystemBus):
    def __init__(self):
        self.published: list = []

    def publish(self, topic, message):
        self.published.append((topic, message))
        return True

    def subscribe(self, topic, callback):
        return True

    def unsubscribe(self, topic):
        return True

    def request(self, topic, message, timeout=30.0):
        self.published.append((topic, message))
        return {"target_response": {"payload": {"test": "ok"}}}

    def request_async(self, topic, message, timeout=30.0):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        fut = loop.create_future()
        fut.set_result(self.request(topic, message, timeout))
        return fut

    def start(self):
        pass

    def stop(self):
        pass


def _make_component(policies: list = None) -> SecurityMonitorComponent:
    bus = DummyBus()
    policies_str = "[]"
    if policies:
        import json
        policies_str = json.dumps(policies)
    return SecurityMonitorComponent(
        component_id="security_monitor_test",
        bus=bus,
        security_policies=policies_str,
    )


def test_proxy_publish_allowed():
    comp = _make_component(policies=[
        {"sender": AUTOPILOT_TOPIC, "topic": MOTORS_TOPIC, "action": "set_target"},
    ])
    msg = {
        "action": "proxy_publish",
        "sender": AUTOPILOT_TOPIC,
        "payload": {
            "target": {"topic": MOTORS_TOPIC, "action": "set_target"},
            "data": {"vx": 1.0, "vy": 0.0, "vz": 0.0},
        },
    }
    result = comp._handle_proxy_publish(msg)
    assert result is not None and result.get("published") is True
    assert len(comp.bus.published) == 1
    topic, published = comp.bus.published[0]
    assert topic == MOTORS_TOPIC
    assert published.get("action") == "set_target"
    assert published.get("payload", {}).get("vx") == 1.0


def test_proxy_publish_denied_no_policy():
    comp = _make_component(policies=[])
    msg = {
        "action": "proxy_publish",
        "sender": AUTOPILOT_TOPIC,
        "payload": {
            "target": {"topic": MOTORS_TOPIC, "action": "set_target"},
            "data": {},
        },
    }
    result = comp._handle_proxy_publish(msg)
    assert result is None
    assert len(comp.bus.published) == 0


def test_security_policies_placeholder_system_name_is_topic_prefix():
    """${SYSTEM_NAME} в JSON должен давать полный префикс v1.*.*, как в prepare_system."""
    policies = json.dumps(
        [{"sender": "${SYSTEM_NAME}.system_monitor", "topic": "${SYSTEM_NAME}.telemetry", "action": "get_state"}]
    )
    comp = SecurityMonitorComponent(
        component_id="sm",
        bus=DummyBus(),
        security_policies=policies,
    )
    expected_sender = f"{topic_prefix()}.system_monitor"
    expected_topic = f"{topic_prefix()}.telemetry"
    assert (expected_sender, expected_topic, "get_state") in comp._policies


def test_policy_wildcard_allows_any_topic_and_action():
    comp = _make_component(policies=[
        {"sender": SYSTEM_MONITOR_TOPIC, "topic": "*", "action": "*"},
    ])
    assert comp._is_allowed(SYSTEM_MONITOR_TOPIC, MOTORS_TOPIC, "set_target")
    assert comp._is_allowed(SYSTEM_MONITOR_TOPIC, NAVIGATION_TOPIC, "get_state")
    assert comp._is_allowed(SYSTEM_MONITOR_TOPIC, "v1.External.Any.topic", "custom_action")


def test_policy_wildcard_topic_only():
    comp = _make_component(policies=[
        {"sender": SYSTEM_MONITOR_TOPIC, "topic": "*", "action": "get_state"},
    ])
    assert comp._is_allowed(SYSTEM_MONITOR_TOPIC, MOTORS_TOPIC, "get_state")
    assert not comp._is_allowed(SYSTEM_MONITOR_TOPIC, MOTORS_TOPIC, "set_target")


def test_proxy_request_allowed():
    comp = _make_component(policies=[
        {"sender": AUTOPILOT_TOPIC, "topic": NAVIGATION_TOPIC, "action": "get_state"},
    ])
    msg = {
        "action": "proxy_request",
        "sender": AUTOPILOT_TOPIC,
        "payload": {
            "target": {"topic": NAVIGATION_TOPIC, "action": "get_state"},
            "data": {},
        },
    }
    result = comp._handle_proxy_request(msg)
    assert result is not None
    assert "target_response" in result


def test_set_policy_forbidden_without_admin():
    comp = _make_component()
    comp._policy_admin_sender = "admin_only"
    msg = {
        "action": "set_policy",
        "sender": "other",
        "payload": {"sender": "x", "topic": "y", "action": "z"},
    }
    result = comp._handle_set_policy(msg)
    assert result is not None and result.get("updated") is False


def test_set_policy_success():
    comp = _make_component()
    comp._policy_admin_sender = "admin"
    msg = {
        "action": "set_policy",
        "sender": "admin",
        "payload": {"sender": "client_a", "topic": JOURNAL_TOPIC, "action": "log_event"},
    }
    result = comp._handle_set_policy(msg)
    assert result is not None and result.get("updated") is True
    assert ("client_a", JOURNAL_TOPIC, "log_event") in comp._policies


def test_list_policies():
    comp = _make_component(policies=[
        {"sender": "a", "topic": "t1", "action": "act1"},
    ])
    result = comp._handle_list_policies({})
    assert result is not None
    assert result["count"] == 1
    assert result["policies"][0]["sender"] == "a"
