"""Тесты system_monitor."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, Optional

import pytest
from systems.agrodron.broker.system_bus import SystemBus
from systems.agrodron.src.system_monitor import config
from systems.agrodron.src.system_monitor.src.system_monitor import SystemMonitorComponent
from systems.agrodron.scripts.proxy_reply import unwrap_proxy_target_response
from systems.agrodron.sdk.topic_utils import topic_for


@pytest.fixture(autouse=True)
def _disable_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYSTEM_MONITOR_HTTP", "0")


SM = topic_for("security_monitor")


class MockBus(SystemBus):
    def __init__(self) -> None:
        self._callbacks: Dict[str, Callable[[Dict[str, Any]], None]] = {}
        self.requests: list = []

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
        if message.get("action") == "proxy_request":
            # Как в MQTT: ответ security_monitor обёрнут в payload (create_response)
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
        return None

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


def _make(bus: MockBus) -> SystemMonitorComponent:
    return SystemMonitorComponent(
        component_id="system_monitor_test",
        bus=bus,
        topic=config.component_topic(),
    )


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
