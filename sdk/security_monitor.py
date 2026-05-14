"""
BaseSecurityMonitor — компонент монитора безопасности для SafeBus.

Слушает топик security.monitor, получает security_check запросы
от SafeBus и возвращает решение (approved / denied).

Подкласс переопределяет check_message() для реализации политики.
По умолчанию всё одобряется (passthrough).

Пример кастомной политики:

    class StrictMonitor(BaseSecurityMonitor):
        def check_message(self, target_topic, action, sender, payload):
            if sender not in ALLOWED_SENDERS:
                return False, f"sender {sender} is not allowed"
            return True, ""
"""
from typing import Dict, Any, Tuple

from sdk.base_component import BaseComponent
from broker.system_bus import SystemBus


class BaseSecurityMonitor(BaseComponent):
    """
    Базовый монитор безопасности.

    Получает от SafeBus запросы security_check с метаданными
    исходящего сообщения и возвращает решение.

    Переопределите check_message() для реализации политики.
    """

    def __init__(
        self,
        bus: SystemBus,
        component_id: str = "security_monitor",
        topic: str = "security.monitor",
    ):
        super().__init__(
            component_id=component_id,
            component_type="security_monitor",
            topic=topic,
            bus=bus,
        )

    def _register_handlers(self):
        self.register_handler("security_check", self._handle_security_check)

    def _handle_security_check(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {})

        approved, reason = self.check_message(
            target_topic=payload.get("target_topic", ""),
            action=payload.get("action", ""),
            sender=payload.get("sender", ""),
            payload=payload.get("payload") or {},
        )

        return {"approved": approved, "reason": reason}

    def check_message(
        self,
        target_topic: str,
        action: str,
        sender: str,
        payload: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Проверяет исходящее сообщение.

        Переопределите для реализации политики безопасности.
        По умолчанию одобряет всё.

        Args:
            target_topic: Целевой топик сообщения.
            action: Action сообщения.
            sender: Отправитель сообщения.
            payload: Данные сообщения.

        Returns:
            (approved, reason). reason заполняется при отказе.
        """
        return True, ""
