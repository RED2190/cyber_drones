"""Unit-тесты компонента security_monitor."""
from broker.system_bus import SystemBus
from components.security_monitor import config
from components.security_monitor.src.security_monitor import SecurityMonitorComponent


class DummyBus(SystemBus):
    def __init__(self):
        self.published: list = []

    def publish(self, topic, message):
        self.published.append((topic, message))
        return True

    def request(self, topic, message, timeout=30.0):
        self.published.append((topic, message))
        return {"target_response": {"payload": {"test": "ok"}}}

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
        {"sender": "autopilot", "topic": "agrodron.motors", "action": "SET_TARGET"},
    ])
    msg = {
        "action": "proxy_publish",
        "sender": "autopilot",
        "payload": {
            "target": {"topic": "agrodron.motors", "action": "SET_TARGET"},
            "data": {"vx": 1.0, "vy": 0.0, "vz": 0.0},
        },
    }
    result = comp._handle_proxy_publish(msg)
    assert result is not None and result.get("published") is True
    assert len(comp.bus.published) == 1
    topic, published = comp.bus.published[0]
    assert topic == "agrodron.motors"
    assert published.get("action") == "SET_TARGET"
    assert published.get("payload", {}).get("vx") == 1.0


def test_proxy_publish_denied_no_policy():
    comp = _make_component(policies=[])
    msg = {
        "action": "proxy_publish",
        "sender": "autopilot",
        "payload": {
            "target": {"topic": "agrodron.motors", "action": "SET_TARGET"},
            "data": {},
        },
    }
    result = comp._handle_proxy_publish(msg)
    assert result is None
    assert len(comp.bus.published) == 0


def test_proxy_request_allowed():
    comp = _make_component(policies=[
        {"sender": "autopilot", "topic": "agrodron.navigation", "action": "get_state"},
    ])
    msg = {
        "action": "proxy_request",
        "sender": "autopilot",
        "payload": {
            "target": {"topic": "agrodron.navigation", "action": "get_state"},
            "data": {},
        },
    }
    # request() в DummyBus возвращает target_response
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
        "payload": {"sender": "client_a", "topic": "agrodron.journal", "action": "LOG_EVENT"},
    }
    result = comp._handle_set_policy(msg)
    assert result is not None and result.get("updated") is True
    assert ("client_a", "agrodron.journal", "LOG_EVENT") in comp._policies


def test_list_policies():
    comp = _make_component(policies=[
        {"sender": "a", "topic": "t1", "action": "act1"},
    ])
    result = comp._handle_list_policies({})
    assert result is not None
    assert result["count"] == 1
    assert result["policies"][0]["sender"] == "a"
