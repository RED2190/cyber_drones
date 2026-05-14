from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

from broker.system_bus import SystemBus
from sdk.base_component import BaseComponent
from systems.agrodron.src.journal_log import publish_journal_event
from systems.agrodron.scripts.proxy_reply import extract_navigation_nav_state_from_target_response
from systems.agrodron.scripts.proxy_reply import unwrap_proxy_target_response

from systems.agrodron.src.telemetry import config


class TelemetryComponent(BaseComponent):
    """
    Компонент телеметрии.

    Собирает состояние с:
    - motors (get_state)
    - sprayer (get_state)
    - navigation (get_state)

    Сбор делается через монитор безопасности (proxy_request). На запрос get_state
    возвращает последний собранный snapshot.
    """

    def __init__(self, component_id: str, bus: SystemBus, topic: str = ""):
        self._lock = threading.Lock()
        self._last_motors: Optional[Dict[str, Any]] = None
        self._last_sprayer: Optional[Dict[str, Any]] = None
        self._last_navigation: Optional[Dict[str, Any]] = None
        self._last_poll_ts: float = 0.0

        self._poll_thread: Optional[threading.Thread] = None
        self._poll_interval_s: float = config.telemetry_poll_interval_s()
        self._request_timeout_s: float = config.telemetry_request_timeout_s()
        self._journal_logged_first_aggregate = False

        super().__init__(
            component_id=component_id,
            component_type="telemetry",
            topic=(topic or config.component_topic()),
            bus=bus,
        )

    @staticmethod
    def _is_trusted_sender(message: Dict[str, Any]) -> bool:
        sender = message.get("sender")
        return isinstance(sender, str) and sender == config.security_monitor_topic()

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

    def _handle_get_state(self, message: Dict[str, Any]) -> Dict[str, Any]:
        if not self._is_trusted_sender(message):
            # Всегда dict, чтобы BaseComponent отправил ответ по reply_to (иначе МБ ждёт до таймаута).
            return {
                "motors": None,
                "sprayer": None,
                "navigation": None,
                "last_poll_ts": 0.0,
                "telemetry_trust_error": True,
                "sender_expected": config.security_monitor_topic(),
                "sender_received": message.get("sender"),
            }
        with self._lock:
            return {
                "motors": dict(self._last_motors) if isinstance(self._last_motors, dict) else None,
                "sprayer": dict(self._last_sprayer) if isinstance(self._last_sprayer, dict) else None,
                "navigation": dict(self._last_navigation) if isinstance(self._last_navigation, dict) else None,
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
        navigation_state = self._proxy_get_state(config.navigation_topic(), "get_state")
        with self._lock:
            if isinstance(motors_state, dict):
                self._last_motors = motors_state
            if isinstance(sprayer_state, dict):
                self._last_sprayer = sprayer_state
            if isinstance(navigation_state, dict):
                self._last_navigation = navigation_state
            self._last_poll_ts = time.time()

        has_any = (
            isinstance(motors_state, dict)
            or isinstance(sprayer_state, dict)
            or isinstance(navigation_state, dict)
        )
        if has_any and not self._journal_logged_first_aggregate:
            self._journal_logged_first_aggregate = True
            publish_journal_event(
                self.bus,
                self.topic,
                "TELEMETRY_AGGREGATE_FIRST_OK",
                source="telemetry",
                details={
                    # true = получен dict от цели; false = таймаут/ошибка proxy, не «режим моторов»
                    "motors_ok": isinstance(motors_state, dict),
                    "sprayer_ok": isinstance(sprayer_state, dict),
                    "navigation_ok": isinstance(navigation_state, dict),
                },
            )

    def _proxy_get_state(self, target_topic: str, target_action: str) -> Optional[Dict[str, Any]]:
        message = {
            "action": "proxy_request",
            "sender": self.topic,
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
        target_response = unwrap_proxy_target_response(response)
        if not isinstance(target_response, dict):
            return None
        inner = target_response.get("payload")
        if not isinstance(inner, dict):
            return target_response
        if target_topic == config.navigation_topic():
            nav = extract_navigation_nav_state_from_target_response(target_response)
            return nav if nav is not None else inner
        return inner
