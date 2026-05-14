"""Unit-тесты компонента security_monitor."""
import asyncio
import json

from broker.system_bus import SystemBus
from systems.agrodron.src.security_monitor import config
from systems.agrodron.src.security_monitor.src.security_monitor import SecurityMonitorComponent
from systems.agrodron.src.topic_utils import topic_for, topic_prefix

AUTOPILOT_TOPIC = topic_for("autopilot")
NAVIGATION_TOPIC = topic_for("navigation")
MOTORS_TOPIC = topic_for("motors")
JOURNAL_TOPIC = topic_for("journal")
SYSTEM_MONITOR_TOPIC = topic_for("system_monitor")
EMERGENSY_TOPIC = topic_for("emergensy")


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


def _make_component(policies: list = None, **kwargs) -> SecurityMonitorComponent:
    bus = DummyBus()
    policies_str = "[]"
    if policies:
        import json
        policies_str = json.dumps(policies)
    return SecurityMonitorComponent(
        component_id="security_monitor_test",
        bus=bus,
        security_policies=policies_str,
        **kwargs,
    )


# ---------------------------------------------------------------- proxy_publish

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


def test_proxy_publish_no_target():
    comp = _make_component(policies=[])
    msg = {
        "action": "proxy_publish",
        "sender": AUTOPILOT_TOPIC,
        "payload": {},
    }
    result = comp._handle_proxy_publish(msg)
    assert result is None


def test_proxy_publish_raw_action():
    comp = _make_component(policies=[
        {"sender": "raw_client", "topic": "target_topic", "action": "__raw__"},
    ])
    msg = {
        "action": "proxy_publish",
        "sender": "raw_client",
        "payload": {
            "target": {"topic": "target_topic", "action": "__raw__"},
            "data": {"custom_key": "custom_val"},
        },
    }
    result = comp._handle_proxy_publish(msg)
    assert result is not None and result.get("published") is True
    _, published = comp.bus.published[-1]
    assert published["custom_key"] == "custom_val"


# ---------------------------------------------------------------- proxy_request

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


def test_proxy_request_denied():
    comp = _make_component(policies=[])
    msg = {
        "action": "proxy_request",
        "sender": AUTOPILOT_TOPIC,
        "payload": {
            "target": {"topic": NAVIGATION_TOPIC, "action": "get_state"},
            "data": {},
        },
    }
    result = comp._handle_proxy_request(msg)
    assert result["ok"] is False
    assert result["error"] == "policy_denied"


def test_proxy_request_no_target():
    comp = _make_component(policies=[])
    msg = {
        "action": "proxy_request",
        "sender": AUTOPILOT_TOPIC,
        "payload": {},
    }
    result = comp._handle_proxy_request(msg)
    assert result["ok"] is False
    assert result["error"] == "no_target_in_payload"


def test_proxy_request_target_timeout():
    bus = DummyBus()
    comp = SecurityMonitorComponent(
        component_id="sm_test",
        bus=bus,
        security_policies=json.dumps([{"sender": AUTOPILOT_TOPIC, "topic": NAVIGATION_TOPIC, "action": "get_state"}]),
    )
    # Override bus.request to return None (timeout)
    comp.bus.request = lambda *a, **kw: None
    msg = {
        "action": "proxy_request",
        "sender": AUTOPILOT_TOPIC,
        "payload": {
            "target": {"topic": NAVIGATION_TOPIC, "action": "get_state"},
            "data": {},
        },
    }
    result = comp._handle_proxy_request(msg)
    assert result["ok"] is False
    assert result["error"] == "target_timeout"


def test_proxy_request_raw_action():
    comp = _make_component(policies=[
        {"sender": "raw_client", "topic": "target_topic", "action": "__raw__"},
    ])
    # Need bus that returns something for the raw request
    comp.bus.request = lambda topic, msg, timeout=30.0: {"raw": "response"}
    msg = {
        "action": "proxy_request",
        "sender": "raw_client",
        "payload": {
            "target": {"topic": "target_topic", "action": "__raw__"},
            "data": {"custom_key": "val"},
        },
    }
    result = comp._handle_proxy_request(msg)
    assert result is not None
    assert "target_response" in result


# ---------------------------------------------------------------- policies

def test_security_policies_placeholder_system_name_is_topic_prefix():
    """${SYSTEM_NAME} в JSON -> topic_prefix (v1.*.*), как у топиков компонентов."""
    policies = json.dumps(
        [{"sender": "${SYSTEM_NAME}.system_monitor", "topic": "${SYSTEM_NAME}.telemetry", "action": "get_state"}]
    )
    comp = SecurityMonitorComponent(
        component_id="sm",
        bus=DummyBus(),
        security_policies=policies,
    )
    assert (
        f"{topic_prefix()}.system_monitor",
        f"{topic_prefix()}.telemetry",
        "get_state",
    ) in comp._policies


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


def test_policy_wildcard_action_only():
    comp = _make_component(policies=[
        {"sender": SYSTEM_MONITOR_TOPIC, "topic": MOTORS_TOPIC, "action": "*"},
    ])
    assert comp._is_allowed(SYSTEM_MONITOR_TOPIC, MOTORS_TOPIC, "anything")
    assert not comp._is_allowed(SYSTEM_MONITOR_TOPIC, NAVIGATION_TOPIC, "anything")


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


def test_set_policy_invalid():
    comp = _make_component()
    comp._policy_admin_sender = "admin"
    result = comp._handle_set_policy({"sender": "admin", "payload": {"sender": "", "topic": "", "action": ""}})
    assert result["updated"] is False
    assert result["error"] == "invalid_policy"


def test_remove_policy():
    comp = _make_component()
    comp._policy_admin_sender = "admin"
    comp._policies.add(("x", "y", "z"))
    msg = {"sender": "admin", "payload": {"sender": "x", "topic": "y", "action": "z"}}
    result = comp._handle_remove_policy(msg)
    assert result["removed"] is True
    assert ("x", "y", "z") not in comp._policies


def test_remove_policy_not_found():
    comp = _make_component()
    comp._policy_admin_sender = "admin"
    msg = {"sender": "admin", "payload": {"sender": "x", "topic": "y", "action": "z"}}
    result = comp._handle_remove_policy(msg)
    assert result["removed"] is False


def test_remove_policy_forbidden():
    comp = _make_component()
    comp._policy_admin_sender = "admin_only"
    result = comp._handle_remove_policy({"sender": "other", "payload": {"sender": "x", "topic": "y", "action": "z"}})
    assert result["removed"] is False
    assert result["error"] == "forbidden"


def test_clear_policies():
    comp = _make_component(policies=[{"sender": "a", "topic": "b", "action": "c"}])
    comp._policy_admin_sender = "admin"
    result = comp._handle_clear_policies({"sender": "admin"})
    assert result["cleared"] is True
    assert result["removed_count"] == 1
    assert len(comp._policies) == 0


def test_clear_policies_forbidden():
    comp = _make_component()
    comp._policy_admin_sender = "admin_only"
    result = comp._handle_clear_policies({"sender": "other"})
    assert result["cleared"] is False
    assert result["error"] == "forbidden"


def test_list_policies():
    comp = _make_component(policies=[
        {"sender": "a", "topic": "t1", "action": "act1"},
    ])
    result = comp._handle_list_policies({})
    assert result is not None
    assert result["count"] == 1
    assert result["policies"][0]["sender"] == "a"


# ---------------------------------------------------------------- parse_policies

def test_parse_policies_csv():
    comp = _make_component()
    result = comp._parse_policies("sender1, topic1, action1 ; sender2, topic2, action2")
    assert len(result) == 2
    assert ("sender1", "topic1", "action1") in result
    assert ("sender2", "topic2", "action2") in result


def test_parse_policies_invalid_csv():
    comp = _make_component()
    result = comp._parse_policies("only_two,parts")
    assert len(result) == 0


def test_parse_policies_empty():
    comp = _make_component()
    result = comp._parse_policies("")
    assert len(result) == 0


def test_parse_policies_json_list_of_lists():
    comp = _make_component()
    raw = json.dumps([["s1", "t1", "a1"], ["s2", "t2", "a2"]])
    result = comp._parse_policies(raw)
    assert len(result) == 2


def test_parse_policies_invalid_json_falls_back_to_csv():
    comp = _make_component()
    raw = "not json; s1, t1, a1"
    result = comp._parse_policies(raw)
    assert ("s1", "t1", "a1") in result


def test_parse_policies_with_system_name_placeholder():
    comp = _make_component()
    tp = topic_prefix()
    raw = json.dumps([{"sender": "${SYSTEM_NAME}.nav", "topic": "${SYSTEM_NAME}.motors", "action": "act"}])
    # The substitution happens in __init__, not in _parse_policies directly.
    # But we can test _parse_policies with already-substituted values.
    raw_sub = raw.replace("${SYSTEM_NAME}", tp)
    result = comp._parse_policies(raw_sub)
    assert (f"{tp}.nav", f"{tp}.motors", "act") in result


# ---------------------------------------------------------------- extract helpers

def test_extract_target():
    comp = _make_component()
    payload = {"target": {"topic": "t", "action": "a"}, "data": {"k": "v"}}
    result = comp._extract_target(payload)
    assert result == ("t", "a", {"k": "v"})


def test_extract_target_no_topic():
    comp = _make_component()
    payload = {"target": {"action": "a"}}
    result = comp._extract_target(payload)
    assert result is None


def test_extract_target_no_action():
    comp = _make_component()
    payload = {"target": {"topic": "t"}}
    result = comp._extract_target(payload)
    assert result is None


def test_extract_target_non_dict_data():
    comp = _make_component()
    payload = {"target": {"topic": "t", "action": "a"}, "data": "not_dict"}
    result = comp._extract_target(payload)
    assert result is not None
    assert result[2] == {}  # data defaults to empty dict


def test_extract_policy():
    comp = _make_component()
    result = comp._extract_policy({"sender": "s", "topic": "t", "action": "a"})
    assert result == ("s", "t", "a")


def test_extract_policy_missing_fields():
    comp = _make_component()
    result = comp._extract_policy({"sender": "", "topic": "", "action": ""})
    assert result is None


# ---------------------------------------------------------------- isolation

def test_isolation_start_from_emergensy():
    comp = _make_component()
    msg = {"sender": EMERGENSY_TOPIC}
    result = comp._handle_isolation_start(msg)
    assert result["activated"] is True
    assert result["mode"] == "ISOLATED"
    assert comp._mode == "ISOLATED"


def test_isolation_start_from_admin():
    comp = _make_component(policy_admin_sender="admin")
    msg = {"sender": "admin"}
    result = comp._handle_isolation_start(msg)
    assert result["activated"] is True
    assert comp._mode == "ISOLATED"


def test_isolation_start_forbidden():
    comp = _make_component()
    msg = {"sender": "random_sender"}
    result = comp._handle_isolation_start(msg)
    assert result["activated"] is False
    assert result["error"] == "forbidden"


def test_isolation_status():
    comp = _make_component()
    result = comp._handle_isolation_status({})
    assert result["mode"] == "NORMAL"


def test_load_emergency_policies():
    comp = _make_component()
    comp._load_emergency_policies()
    assert comp._mode == "ISOLATED"
    # Should have 5 emergency policies
    assert len(comp._policies) == 5


def test_policy_to_dict():
    comp = _make_component()
    result = comp._policy_to_dict(("sender_x", "topic_y", "action_z"))
    assert result == {"sender": "sender_x", "topic": "topic_y", "action": "action_z"}


# ---------------------------------------------------------------- _is_allowed

def test_is_allowed_exact_match():
    comp = _make_component(policies=[
        {"sender": "s1", "topic": "t1", "action": "a1"},
    ])
    assert comp._is_allowed("s1", "t1", "a1") is True
    assert comp._is_allowed("s1", "t1", "a2") is False
    assert comp._is_allowed("s2", "t1", "a1") is False


def test_is_allowed_no_match():
    comp = _make_component(policies=[])
    assert comp._is_allowed("any", "any", "any") is False


# ---------------------------------------------------------------- can_manage_policies

def test_can_manage_policies():
    comp = _make_component(policy_admin_sender="admin")
    assert comp._can_manage_policies("admin") is True
    assert comp._can_manage_policies("other") is False


def test_can_manage_policies_no_admin():
    comp = _make_component()
    assert comp._can_manage_policies("anyone") is False
