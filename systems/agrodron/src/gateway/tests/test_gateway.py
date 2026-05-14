"""Unit-тесты компонента AgrodronGateway."""
import asyncio
import os
from typing import Any, Dict, Optional

from broker.system_bus import SystemBus
from systems.agrodron.src.gateway.src.gateway import AgrodronGateway
from systems.agrodron.src.gateway.topics import ComponentTopics, GatewayActions, SystemTopics


class MockBus(SystemBus):
    def __init__(self):
        self.published: list = []
        self._request_response: Optional[Dict[str, Any]] = None

    def set_request_response(self, resp: Dict[str, Any]):
        self._request_response = resp

    def publish(self, topic: str, message: Dict[str, Any]) -> bool:
        self.published.append((topic, message))
        return True

    def subscribe(self, topic: str, callback) -> bool:
        return True

    def unsubscribe(self, topic: str) -> bool:
        return True

    def request(self, topic: str, message: Dict[str, Any], timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        self.published.append((topic, message))
        return self._request_response

    def request_async(self, topic: str, message: Dict[str, Any], timeout: float = 30.0):
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


def _make_gateway(bus: MockBus = None) -> AgrodronGateway:
    if bus is None:
        bus = MockBus()
    return AgrodronGateway(system_id="agrodron_test", bus=bus)


def _msg(action: str, payload: dict = None, sender: str = "test_sender") -> dict:
    return {"action": action, "sender": sender, "payload": payload or {}}


# ---------------------------------------------------------------- extract_sender

def test_extract_sender_from_message():
    gw = _make_gateway()
    assert gw._extract_sender({"sender": "  my_sender  "}) == "my_sender"


def test_extract_sender_empty_uses_default():
    gw = _make_gateway()
    result = gw._extract_sender({"sender": ""})
    assert result == gw._default_sender


def test_extract_sender_missing_key():
    gw = _make_gateway()
    result = gw._extract_sender({})
    assert result == gw._default_sender


def test_default_sender_from_env():
    saved = os.environ.pop("AGRODRON_GATEWAY_SENDER", None)
    saved2 = os.environ.pop("NUS_TOPIC", None)
    try:
        os.environ["AGRODRON_GATEWAY_SENDER"] = "custom_sender"
        gw = _make_gateway()
        assert gw._default_sender == "custom_sender"
    finally:
        if saved is not None:
            os.environ["AGRODRON_GATEWAY_SENDER"] = saved
        else:
            os.environ.pop("AGRODRON_GATEWAY_SENDER", None)
        if saved2 is not None:
            os.environ["NUS_TOPIC"] = saved2


def test_default_sender_fallback_nus_topic():
    saved = os.environ.pop("AGRODRON_GATEWAY_SENDER", None)
    saved2 = os.environ.pop("NUS_TOPIC", None)
    try:
        os.environ["NUS_TOPIC"] = "nus_topic_val"
        gw = _make_gateway()
        assert gw._default_sender == "nus_topic_val"
    finally:
        if saved is not None:
            os.environ["AGRODRON_GATEWAY_SENDER"] = saved
        else:
            os.environ.pop("AGRODRON_GATEWAY_SENDER", None)
        if saved2 is not None:
            os.environ["NUS_TOPIC"] = saved2
        else:
            os.environ.pop("NUS_TOPIC", None)


def test_default_sender_fallback_gateway():
    saved = os.environ.pop("AGRODRON_GATEWAY_SENDER", None)
    saved2 = os.environ.pop("NUS_TOPIC", None)
    try:
        gw = _make_gateway()
        assert gw._default_sender == "gateway"
    finally:
        if saved is not None:
            os.environ["AGRODRON_GATEWAY_SENDER"] = saved
        if saved2 is not None:
            os.environ["NUS_TOPIC"] = saved2


# ---------------------------------------------------------------- proxy_request

def test_proxy_request_returns_response():
    bus = MockBus()
    bus.set_request_response({"target_response": {"ok": True}})
    gw = _make_gateway(bus)
    result = gw._proxy_request("sender_x", "target.topic", "action_y", {"key": "val"})
    assert result == {"target_response": {"ok": True}}
    # Should have made a request to security_monitor
    assert len(bus.published) == 1
    topic, msg = bus.published[0]
    assert topic == ComponentTopics.SECURITY_MONITOR
    assert msg["action"] == "proxy_request"
    assert msg["sender"] == "sender_x"
    assert msg["payload"]["target"]["topic"] == "target.topic"
    assert msg["payload"]["target"]["action"] == "action_y"
    assert msg["payload"]["data"] == {"key": "val"}


def test_proxy_request_sm_unavailable():
    bus = MockBus()
    bus.set_request_response(None)
    gw = _make_gateway(bus)
    result = gw._proxy_request("s", "t", "a", {})
    assert result["ok"] is False
    assert result["error"] == "security_monitor_unavailable"


# ---------------------------------------------------------------- unwrap_target_response

def test_unwrap_target_response_top_level():
    resp = {"target_response": {"ok": True, "data": 42}}
    result = AgrodronGateway._unwrap_target_response(resp)
    assert result == {"ok": True, "data": 42}


def test_unwrap_target_response_nested():
    resp = {"payload": {"target_response": {"ok": True}}}
    result = AgrodronGateway._unwrap_target_response(resp)
    assert result == {"ok": True}


def test_unwrap_target_response_no_target():
    resp = {"ok": True, "other": "data"}
    result = AgrodronGateway._unwrap_target_response(resp)
    assert result == resp  # returns original


def test_unwrap_target_response_payload_no_nested():
    resp = {"payload": {"ok": True}}
    result = AgrodronGateway._unwrap_target_response(resp)
    assert result == resp  # no target_response found, returns original


# ---------------------------------------------------------------- extract_mission_payload

def test_extract_mission_payload():
    payload = {"mission_id": "m1", "wpl_content": "WPL data"}
    mid, wpl = AgrodronGateway._extract_mission_payload(payload)
    assert mid == "m1"
    assert wpl == "WPL data"


def test_extract_mission_payload_missing():
    mid, wpl = AgrodronGateway._extract_mission_payload({})
    assert mid is None
    assert wpl is None


# ---------------------------------------------------------------- handlers

def test_handle_load_mission():
    bus = MockBus()
    bus.set_request_response({
        "target_response": {"ok": True, "mission_id": "m1"},
    })
    gw = _make_gateway(bus)
    result = gw._handle_load_mission(_msg("load_mission", {"mission_id": "m1", "wpl_content": "WPL"}))
    assert result["ok"] is True
    assert result["mission_id"] == "m1"


def test_handle_load_mission_nested_response():
    bus = MockBus()
    bus.set_request_response({
        "payload": {
            "target_response": {"ok": True, "mission_id": "m1"},
        },
    })
    gw = _make_gateway(bus)
    result = gw._handle_load_mission(_msg("load_mission", {"mission_id": "m1", "wpl_content": "WPL"}))
    assert result["ok"] is True


def test_handle_validate_only():
    bus = MockBus()
    bus.set_request_response({
        "target_response": {"ok": True, "valid": True},
    })
    gw = _make_gateway(bus)
    result = gw._handle_validate_only(_msg("validate_only", {"mission_id": "m1", "wpl_content": "WPL"}))
    assert result["ok"] is True


def test_handle_cmd():
    bus = MockBus()
    bus.set_request_response({
        "target_response": {"ok": True, "state": "EXECUTING"},
    })
    gw = _make_gateway(bus)
    result = gw._handle_cmd(_msg("cmd", {"command": "START"}))
    assert result["ok"] is True
    assert result["state"] == "EXECUTING"


def test_handle_get_state():
    bus = MockBus()
    bus.set_request_response({
        "target_response": {"motors": {"mode": "IDLE"}, "sprayer": None},
    })
    gw = _make_gateway(bus)
    result = gw._handle_get_state(_msg("get_state"))
    assert "motors" in result


def test_handle_load_mission_empty_payload():
    bus = MockBus()
    bus.set_request_response({"target_response": {"ok": True}})
    gw = _make_gateway(bus)
    result = gw._handle_load_mission(_msg("load_mission", {}))
    # Should still work with None mission_id and wpl_content
    assert result["ok"] is True


def test_handle_load_mission_sm_unavailable():
    bus = MockBus()
    bus.set_request_response(None)
    gw = _make_gateway(bus)
    result = gw._handle_load_mission(_msg("load_mission", {"mission_id": "m1"}))
    assert result["ok"] is False
    assert result["error"] == "security_monitor_unavailable"
