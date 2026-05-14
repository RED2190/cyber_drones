"""Тесты system_monitor."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, Optional

import pytest
from broker.system_bus import SystemBus
from systems.agrodron.src.system_monitor import config
from systems.agrodron.src.system_monitor.src.system_monitor import SystemMonitorComponent
from systems.agrodron.scripts.proxy_reply import unwrap_proxy_target_response
from systems.agrodron.src.topic_utils import topic_for


@pytest.fixture(autouse=True)
def _disable_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYSTEM_MONITOR_HTTP", "0")


SM = topic_for("security_monitor")


class MockBus(SystemBus):
    def __init__(self) -> None:
        self._callbacks: Dict[str, Callable[[Dict[str, Any]], None]] = {}
        self.requests: list = []
        self._request_response: Optional[Dict[str, Any]] = None

    def set_request_response(self, resp: Dict[str, Any]):
        self._request_response = resp

    def publish(self, topic: str, message: Dict[str, Any]) -> bool:
        return True

    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> bool:
        self._callbacks[topic] = callback
        return True

    def unsubscribe(self, topic: str) -> bool:
        self._callbacks.pop(topic, None)
        return True

    def request(
        self,
        topic: str,
        message: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Optional[Dict[str, Any]]:
        self.requests.append((topic, message))
        if self._request_response is not None:
            return self._request_response
        if message.get("action") == "proxy_request":
            return {
                "action": "response",
                "payload": {
                    "target_topic": "t",
                    "target_action": "get_state",
                    "target_response": {
                        "payload": {
                            "motors": {"mode": "IDLE"},
                            "sprayer": None,
                            "navigation": None,
                            "last_poll_ts": 1.0,
                        },
                    },
                },
            }
        return self._request_response  # None by default

    def request_async(
        self,
        topic: str,
        message: Dict[str, Any],
        timeout: float = 30.0,
    ):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        fut = loop.create_future()
        fut.set_result(self.request(topic, message, timeout))
        return fut

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def inject_journal(self, msg: Dict[str, Any]) -> None:
        cb = self._callbacks.get(config.journal_topic())
        if cb:
            cb(msg)


def _make(bus: MockBus = None) -> SystemMonitorComponent:
    if bus is None:
        bus = MockBus()
    return SystemMonitorComponent(
        component_id="system_monitor_test",
        bus=bus,
        topic=config.component_topic(),
    )


# ---------------------------------------------------------------- journal tap

def test_journal_tap_collects_log_event() -> None:
    bus = MockBus()
    comp = _make(bus)
    comp.start()
    bus.inject_journal(
        {
            "action": "log_event",
            "sender": SM,
            "payload": {"event": "E1", "source": "x"},
        }
    )
    snap = comp._snapshot()
    assert len(snap["journal_events"]) == 1
    assert snap["journal_events"][0]["payload"]["event"] == "E1"
    comp.stop()


def test_journal_tap_ignores_non_log_event() -> None:
    bus = MockBus()
    comp = _make(bus)
    comp.start()
    bus.inject_journal(
        {
            "action": "other_action",
            "sender": SM,
            "payload": {"event": "E1"},
        }
    )
    snap = comp._snapshot()
    assert len(snap["journal_events"]) == 0
    comp.stop()


def test_journal_tap_multiple_events() -> None:
    bus = MockBus()
    comp = _make(bus)
    comp.start()
    for i in range(5):
        bus.inject_journal({
            "action": "log_event",
            "sender": SM,
            "payload": {"event": f"E{i}"},
        })
    snap = comp._snapshot()
    assert len(snap["journal_events"]) == 5
    comp.stop()


def test_journal_event_has_timestamp() -> None:
    bus = MockBus()
    comp = _make(bus)
    comp.start()
    bus.inject_journal({
        "action": "log_event",
        "sender": SM,
        "payload": {"event": "E1"},
    })
    snap = comp._snapshot()
    assert "ts" in snap["journal_events"][0]
    comp.stop()


# ---------------------------------------------------------------- telemetry

def test_fetch_telemetry_via_proxy() -> None:
    bus = MockBus()
    comp = _make(bus)
    comp.start()
    out, dbg = comp._fetch_telemetry()
    assert out is not None
    assert dbg is None
    assert out.get("motors", {}).get("mode") == "IDLE"
    assert bus.requests
    comp.stop()


def test_fetch_telemetry_non_dict_response() -> None:
    bus = MockBus()
    # Override the default proxy_request handler to return None
    bus._request_response = None
    bus.request = lambda topic, message, timeout=30.0: None
    comp = _make(bus)
    comp.start()
    out, dbg = comp._fetch_telemetry()
    assert out is None
    assert dbg is not None
    comp.stop()


def test_fetch_telemetry_proxy_failed() -> None:
    bus = MockBus()
    bus.set_request_response({
        "payload": {"ok": False, "error": "policy_denied", "target_topic": "t"},
    })
    comp = _make(bus)
    comp.start()
    out, dbg = comp._fetch_telemetry()
    assert out is None
    assert dbg is not None
    comp.stop()


def test_fetch_telemetry_no_target_response() -> None:
    bus = MockBus()
    bus.set_request_response({
        "some_key": "value",
    })
    comp = _make(bus)
    comp.start()
    out, dbg = comp._fetch_telemetry()
    assert out is None
    assert dbg is not None
    comp.stop()


def test_fetch_telemetry_no_snapshot_fields() -> None:
    bus = MockBus()
    bus.set_request_response({
        "target_response": {
            "payload": {"unrelated_key": "value"},
        },
    })
    comp = _make(bus)
    comp.start()
    out, dbg = comp._fetch_telemetry()
    assert out is None
    assert dbg is not None
    comp.stop()


def test_fetch_telemetry_trust_error() -> None:
    bus = MockBus()
    bus.set_request_response({
        "target_response": {
            "payload": {
                "motors": {"mode": "IDLE"},
                "last_poll_ts": 1.0,
                "telemetry_trust_error": True,
                "sender_expected": "expected",
                "sender_received": "wrong",
            },
        },
    })
    comp = _make(bus)
    comp.start()
    out, dbg = comp._fetch_telemetry()
    assert out is None
    assert dbg is not None
    assert "telemetry_trust_error" in dbg or "sender" in dbg
    comp.stop()


# ---------------------------------------------------------------- _extract_telemetry_snapshot

def test_extract_telemetry_snapshot_from_payload():
    target_resp = {
        "payload": {
            "motors": {"mode": "IDLE"},
            "sprayer": None,
            "navigation": None,
            "last_poll_ts": 1.0,
        },
    }
    result = SystemMonitorComponent._extract_telemetry_snapshot(target_resp)
    assert result is not None
    assert result["motors"]["mode"] == "IDLE"


def test_extract_telemetry_snapshot_from_root():
    target_resp = {
        "motors": {"mode": "IDLE"},
        "last_poll_ts": 1.0,
    }
    result = SystemMonitorComponent._extract_telemetry_snapshot(target_resp)
    assert result is not None
    assert result["motors"]["mode"] == "IDLE"


def test_extract_telemetry_snapshot_no_valid_fields():
    target_resp = {"unrelated": "data"}
    result = SystemMonitorComponent._extract_telemetry_snapshot(target_resp)
    assert result is None


def test_extract_telemetry_snapshot_with_navigation():
    target_resp = {
        "navigation": {"lat": 60.0},
        "last_poll_ts": 1.0,
    }
    result = SystemMonitorComponent._extract_telemetry_snapshot(target_resp)
    assert result is not None


# ---------------------------------------------------------------- snapshot

def test_snapshot_structure():
    bus = MockBus()
    comp = _make(bus)
    comp.start()
    snap = comp._snapshot()
    assert "journal_events" in snap
    assert "telemetry" in snap
    assert "telemetry_ts" in snap
    assert "telemetry_error" in snap
    assert "telemetry_debug" in snap
    assert "component_id" in snap
    assert snap["component_id"] == "system_monitor_test"
    comp.stop()


# ---------------------------------------------------------------- unwrap

def test_unwrap_proxy_accepts_flat_target_response() -> None:
    """Совместимость с моками / плоским ответом."""
    flat = {
        "target_response": {
            "payload": {"motors": {"mode": "X"}, "last_poll_ts": 0.0},
        }
    }
    tr = unwrap_proxy_target_response(flat)
    assert tr is not None
    assert tr.get("payload", {}).get("motors", {}).get("mode") == "X"


def test_unwrap_proxy_with_nested_payload():
    resp = {
        "payload": {
            "target_response": {
                "payload": {"motors": {"mode": "Y"}, "last_poll_ts": 1.0},
            },
        },
    }
    tr = unwrap_proxy_target_response(resp)
    assert tr is not None


def test_unwrap_proxy_none():
    assert unwrap_proxy_target_response(None) is None


def test_unwrap_proxy_non_dict():
    assert unwrap_proxy_target_response("string") is None


# ---------------------------------------------------------------- start/stop

def test_start_subscribes_and_stop_unsubscribes():
    bus = MockBus()
    comp = _make(bus)
    comp.start()
    # Should have subscribed to journal topic
    assert config.journal_topic() in bus._callbacks
    comp.stop()
    # After stop, callback should be removed
    assert config.journal_topic() not in bus._callbacks
