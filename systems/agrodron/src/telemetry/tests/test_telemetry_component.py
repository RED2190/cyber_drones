"""Unit-тесты компонента telemetry."""
import asyncio
from broker.system_bus import SystemBus
from systems.agrodron.src.telemetry.src.telemetry import TelemetryComponent
from systems.agrodron.src.telemetry import config

SM_TOPIC = config.security_monitor_topic()


class DummyBus(SystemBus):
    def __init__(self):
        self.published: list = []
        self._request_response = None

    def publish(self, topic, message):
        self.published.append((topic, message))
        return True

    def subscribe(self, topic, callback):
        return True

    def unsubscribe(self, topic):
        return True

    def request(self, topic, message, timeout=30.0):
        self.published.append((topic, message))
        return self._request_response

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


def _make_component() -> TelemetryComponent:
    bus = DummyBus()
    return TelemetryComponent(component_id="telemetry_test", bus=bus)


def test_get_state_trust_error_for_untrusted():
    comp = _make_component()
    msg = {"action": "get_state", "sender": "unknown", "payload": {}}
    result = comp._handle_get_state(msg)
    assert result.get("telemetry_trust_error") is True
    assert result.get("sender_received") == "unknown"


def test_get_state_returns_snapshot_for_trusted():
    comp = _make_component()
    comp._last_motors = {"mode": "IDLE", "temperature_c": 50.0}
    comp._last_sprayer = {"state": "OFF"}
    comp._last_navigation = {"lat": 60.0, "lon": 30.0}
    msg = {"action": "get_state", "sender": SM_TOPIC, "payload": {}}
    result = comp._handle_get_state(msg)
    assert result is not None
    assert result["motors"]["mode"] == "IDLE"
    assert result["sprayer"]["state"] == "OFF"
    assert result["navigation"]["lon"] == 30.0
    assert "last_poll_ts" in result


def test_get_state_empty_before_poll():
    comp = _make_component()
    msg = {"action": "get_state", "sender": SM_TOPIC, "payload": {}}
    result = comp._handle_get_state(msg)
    assert result is not None
    assert result["motors"] is None
    assert result["sprayer"] is None
    assert result["navigation"] is None


def test_proxy_get_state_returns_payload_from_response():
    comp = _make_component()
    comp.bus._request_response = {
        "target_response": {"payload": {"mode": "TRACKING"}},
    }
    out = comp._proxy_get_state("agrodron.motors", "get_state")
    assert out == {"mode": "TRACKING"}


def test_proxy_get_state_accepts_flat_component_dict():
    """motors/sprayer возвращают плоский dict без ключа payload."""
    comp = _make_component()
    comp.bus._request_response = {
        "target_response": {"mode": "IDLE", "temperature_c": 40.0},
    }
    out = comp._proxy_get_state("agrodron.motors", "get_state")
    assert out == {"mode": "IDLE", "temperature_c": 40.0}


def test_proxy_get_state_returns_none_on_bad_response():
    comp = _make_component()
    comp.bus._request_response = None
    out = comp._proxy_get_state("agrodron.motors", "get_state")
    assert out is None
