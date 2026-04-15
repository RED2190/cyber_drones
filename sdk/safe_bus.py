"""
SafeBus — обёртка над SystemBus с проверкой через монитор безопасности.

Перехватывает publish() и request(): каждое сообщение проходит
security_check через SecurityMonitor перед отправкой.

Включается через SAFE_BUS_ENABLED=true в .env системы.
Если переменная не задана — используется обычный bus.

Использование:
    inner = create_system_bus(client_id="my_system")
    bus = SafeBus(inner)

Или автоматически: SAFE_BUS_ENABLED=true в окружении.
"""
import os
import asyncio
from typing import Callable, Dict, Any, Optional
from datetime import datetime, timezone

from broker.system_bus import SystemBus

SECURITY_MONITOR_TOPIC = "security.monitor"
DEAD_LETTER_TOPIC = "errors.dead_letters"

_SKIP_ACTIONS = frozenset({"response", "dead_letter", "security_blocked"})


class SafeBus(SystemBus):
    """
    Обёртка над SystemBus: все publish/request проходят security_check
    через SecurityMonitor. Служебные сообщения (response, dead_letter)
    проходят без проверки.
    """

    def __init__(
        self,
        inner: SystemBus,
        monitor_topic: Optional[str] = None,
        check_timeout: float = 5.0,
    ):
        self._inner = inner
        self._monitor_topic = monitor_topic or os.environ.get(
            "SECURITY_MONITOR_TOPIC", SECURITY_MONITOR_TOPIC,
        )
        self._check_timeout = check_timeout

    # ── Делегирование ───────────────────────────────────────────────

    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> bool:
        return self._inner.subscribe(topic, callback)

    def unsubscribe(self, topic: str) -> bool:
        return self._inner.unsubscribe(topic)

    def start(self) -> None:
        return self._inner.start()

    def stop(self) -> None:
        return self._inner.stop()

    def request_async(
        self,
        topic: str,
        message: Dict[str, Any],
        timeout: float = 30.0,
    ) -> "asyncio.Future[Optional[Dict[str, Any]]]":
        return self._inner.request_async(topic, message, timeout=timeout)

    # ── Перехват: publish ───────────────────────────────────────────

    def publish(self, topic: str, message: Dict[str, Any]) -> bool:
        if self._should_skip(topic, message):
            return self._inner.publish(topic, message)

        approved, reason = self._check(topic, message)
        if not approved:
            print(f"[SafeBus] BLOCKED publish → {topic}: {reason}")
            self._inner.publish(DEAD_LETTER_TOPIC, {
                "action": "security_blocked",
                "sender": "safe_bus",
                "error": reason,
                "target_topic": topic,
                "original_action": message.get("action"),
                "original_sender": message.get("sender"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return False

        return self._inner.publish(topic, message)

    # ── Перехват: request ───────────────────────────────────────────

    def request(
        self,
        topic: str,
        message: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Optional[Dict[str, Any]]:
        if self._should_skip(topic, message):
            return self._inner.request(topic, message, timeout=timeout)

        approved, reason = self._check(topic, message)
        if not approved:
            print(f"[SafeBus] BLOCKED request → {topic}: {reason}")
            return None

        return self._inner.request(topic, message, timeout=timeout)

    # ── Внутренняя логика ───────────────────────────────────────────

    def _should_skip(self, topic: str, message: Dict[str, Any]) -> bool:
        if topic == self._monitor_topic:
            return True
        if topic == DEAD_LETTER_TOPIC:
            return True
        action = message.get("action", "") if isinstance(message, dict) else ""
        if action in _SKIP_ACTIONS:
            return True
        return False

    def _check(self, target_topic: str, message: Dict[str, Any]) -> tuple:
        response = self._inner.request(
            self._monitor_topic,
            {
                "action": "security_check",
                "sender": "safe_bus",
                "payload": {
                    "target_topic": target_topic,
                    "action": message.get("action"),
                    "sender": message.get("sender"),
                    "payload": message.get("payload"),
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            timeout=self._check_timeout,
        )

        if response is None:
            return False, "security monitor unavailable"

        if response.get("success"):
            payload = response.get("payload", {})
            return payload.get("approved", False), payload.get("reason", "")

        return False, response.get("error", "monitor error")
