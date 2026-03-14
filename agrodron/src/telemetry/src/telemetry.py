from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

from broker.system_bus import SystemBus
from sdk.base_component import BaseComponent

from components.telemetry import config


class TelemetryComponent(BaseComponent):
    """
    Компонент телеметрии.

    Собирает состояние с:
    - motors (get_state)
    - sprayer (get_state)

    Сбор делается через монитор безопасности (proxy_request). На запрос get_state
    возвращает последний собранный snapshot.
    """

    def __init__(self, component_id: str, bus: SystemBus, topic: str = ""):
        self._lock = threading.Lock()
        self._last_motors: Optional[Dict[str, Any]] = None
        self._last_sprayer: Optional[Dict[str, Any]] = None
        self._last_poll_ts: float = 0.0

        self._poll_thread: Optional[threading.Thread] = None
        self._poll_interval_s: float = config.telemetry_poll_interval_s()
        self._request_timeout_s: float = config.telemetry_request_timeout_s()

        super().__init__(
            component_id=component_id,
            component_type="telemetry",
            topic=(topic or config.component_topic()),
            bus=bus,
        )

    @staticmethod
    def _is_trusted_sender(message: Dict[str, Any]) -> bool:
        sender = message.get("sender")
        return isinstance(sender, str) and sender.startswith("security_monitor")

    def _register_handlers(self) -> None:
        self.register_handler("get_state", self._handle_get_state)

    def start(self) -> None:
        super().start()
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            name=f"{self.component_id}_poll",
            daemon=True,
        )
        self._poll_thread.start()

    def _handle_get_state(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._is_trusted_sender(message):
            return None
        with self._lock:
            return {
                "motors": dict(self._last_motors) if isinstance(self._last_motors, dict) else None,
                "sprayer": dict(self._last_sprayer) if isinstance(self._last_sprayer, dict) else None,
                "last_poll_ts": self._last_poll_ts,
            }

    def _poll_loop(self) -> None:
        while self._running:
            try:
                self._poll_once()
            except Exception as exc:
                print(f"[{self.component_id}] telemetry poll error: {exc}")
            time.sleep(self._poll_interval_s)

    def _poll_once(self) -> None:
        motors_state = self._proxy_get_state(config.motors_topic(), config.motors_get_state_action())
        sprayer_state = self._proxy_get_state(config.sprayer_topic(), config.sprayer_get_state_action())
        with self._lock:
            if isinstance(motors_state, dict):
                self._last_motors = motors_state
            if isinstance(sprayer_state, dict):
                self._last_sprayer = sprayer_state
            self._last_poll_ts = time.time()

    def _proxy_get_state(self, target_topic: str, target_action: str) -> Optional[Dict[str, Any]]:
        message = {
            "action": "proxy_request",
            "sender": self.component_id,
            "payload": {
                "target": {"topic": target_topic, "action": target_action},
                "data": {},
            },
        }
        response = self.bus.request(
            config.security_monitor_topic(),
            message,
            timeout=self._request_timeout_s,
        )
        if not isinstance(response, dict):
            return None
        target_response = response.get("target_response")
        if not isinstance(target_response, dict):
            return None
        payload = target_response.get("payload")
        return payload if isinstance(payload, dict) else None

