"""Unit-тесты компонента telemetry."""
from broker.system_bus import SystemBus
from components.telemetry.src.telemetry import TelemetryComponent


class DummyBus(SystemBus):
    def __init__(self):
        self.published: list = []
        self._request_response = None

    def publish(self, topic, message):
        self.published.append((topic, message))
        return True

    def request(self, topic, message, timeout=30.0):
        self.published.append((topic, message))
        return self._request_response

    def start(self):
        pass

    def stop(self):
        pass


def _make_component() -> TelemetryComponent:
    bus = DummyBus()
    return TelemetryComponent(component_id="telemetry_test", bus=bus)


def test_get_state_returns_none_for_untrusted():
    comp = _make_component()
    msg = {"action": "get_state", "sender": "unknown", "payload": {}}
    result = comp._handle_get_state(msg)
    assert result is None


def test_get_state_returns_snapshot_for_trusted():
    comp = _make_component()
    comp._last_motors = {"mode": "IDLE", "temperature_c": 50.0}
    comp._last_sprayer = {"state": "OFF"}
    msg = {"action": "get_state", "sender": "security_monitor_test", "payload": {}}
    result = comp._handle_get_state(msg)
    assert result is not None
    assert result["motors"]["mode"] == "IDLE"
    assert result["sprayer"]["state"] == "OFF"
    assert "last_poll_ts" in result


def test_get_state_empty_before_poll():
    comp = _make_component()
    msg = {"action": "get_state", "sender": "security_monitor_test", "payload": {}}
    result = comp._handle_get_state(msg)
    assert result is not None
    assert result["motors"] is None
    assert result["sprayer"] is None


def test_proxy_get_state_returns_payload_from_response():
    comp = _make_component()
    comp.bus._request_response = {
        "target_response": {"payload": {"mode": "TRACKING"}},
    }
    out = comp._proxy_get_state("agrodron.motors", "get_state")
    assert out == {"mode": "TRACKING"}


def test_proxy_get_state_returns_none_on_bad_response():
    comp = _make_component()
    comp.bus._request_response = None
    out = comp._proxy_get_state("agrodron.motors", "get_state")
    assert out is None
