from typing import Any, Dict, Optional

from sdk.base_component import BaseComponent
from broker.system_bus import SystemBus
from components.emergensy import config


class EmergenseyComponent(BaseComponent):
    """
    Компонент экстренных ситуаций.

    Получает события от ограничителя (через брокер/монитор) и инициирует
    аварийный протокол: изоляция через монитор безопасности, выключение
    опрыскивателя, посадка, логирование события.
    """

    def __init__(
        self,
        component_id: str,
        bus: SystemBus,
        topic: str = "",
        security_monitor_topic: str = "",
    ):
        self._security_monitor_topic = security_monitor_topic or config.security_monitor_topic()
        self._active: bool = False

        super().__init__(
            component_id=component_id,
            component_type="emergensy",
            topic=(topic or config.component_topic()),
            bus=bus,
        )

    # ------------------------------------------------------------------ utils

    @staticmethod
    def _is_trusted_sender(message: Dict[str, Any]) -> bool:
        sender = message.get("sender")
        # Сценарий: события об аварии приходят через монитор безопасности.
        return isinstance(sender, str) and sender.startswith("security_monitor")

    # ------------------------------------------------------------ registration

    def _register_handlers(self) -> None:
        self.register_handler("limiter_event", self._handle_limiter_event)
        self.register_handler("get_state", self._handle_get_state)

    # ---------------------------------------------------------------- handlers

    def _handle_limiter_event(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._is_trusted_sender(message):
            return None

        payload = message.get("payload") or {}
        event = str(payload.get("event") or "")
        if event != "EMERGENCY_LAND_REQUIRED":
            return {"ok": False, "ignored": True}

        mission_id = payload.get("mission_id")
        details = payload.get("details") or {}

        self._active = True

        # 1. Запрос изоляции в монитор безопасности
        isolation_msg = {
            "action": "ISOLATION_START",
            "sender": self.component_id,
            "payload": {"reason": "LIMITER_EMERGENCY", "mission_id": mission_id},
        }
        self.bus.publish(self._security_monitor_topic, isolation_msg)

        # 2. Команда опрыскивателю на закрытие распыления (через proxy_publish)
        sprayer_cmd = {
            "action": "proxy_publish",
            "sender": self.component_id,
            "payload": {
                "target": {
                    "topic": config.topic_for("sprayer"),
                    "action": "SET_SPRAY",
                },
                "data": {"spray": False, "reason": "emergency"},
            },
        }
        self.bus.publish(self._security_monitor_topic, sprayer_cmd)

        # 3. Команда приводам на посадку (через proxy_publish)
        motors_cmd = {
            "action": "proxy_publish",
            "sender": self.component_id,
            "payload": {
                "target": {
                    "topic": config.topic_for("motors"),
                    "action": "LAND",
                },
                "data": {"mode": "AUTO_LAND", "reason": "emergency"},
            },
        }
        self.bus.publish(self._security_monitor_topic, motors_cmd)

        # 4. Логирование события через журнал (через proxy_publish)
        journal_msg = {
            "action": "proxy_publish",
            "sender": self.component_id,
            "payload": {
                "target": {
                    "topic": config.topic_for("journal"),
                    "action": "LOG_EVENT",
                },
                "data": {
                    "event": "EMERGENCY_PROTOCOL_STARTED",
                    "mission_id": mission_id,
                    "details": details,
                },
            },
        }
        self.bus.publish(self._security_monitor_topic, journal_msg)

        return {"ok": True}

    def _handle_get_state(self, message: Dict[str, Any]) -> Dict[str, Any]:
        return {"active": self._active}

