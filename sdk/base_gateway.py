"""
Базовый класс Gateway — координатор системы для межсистемного общения.

Отправитель знает только топик системы и action.
Gateway по таблице ACTION_ROUTING определяет, какому внутреннему
компоненту переслать запрос, и возвращает ответ отправителю.
"""
from typing import Dict, Any, Optional

from sdk.base_system import BaseSystem
from broker.system_bus import SystemBus


class BaseGateway(BaseSystem):
    """
    Наследник BaseSystem с автоматической маршрутизацией по ACTION_ROUTING.

    Подкласс определяет ACTION_ROUTING — dict {action: component_topic}.
    Gateway регистрирует хендлер для каждого action и проксирует
    запрос к внутреннему компоненту.

    Пример:
        class MyGateway(BaseGateway):
            ACTION_ROUTING = {
                "check_zone": "components.cert_checker",
                "get_position": "components.gps_sensor",
            }
    """

    ACTION_ROUTING: Dict[str, str] = {}
    PROXY_TIMEOUT: float = 10.0

    def __init__(
        self,
        system_id: str,
        system_type: str,
        topic: str,
        bus: SystemBus,
        health_port: Optional[int] = None,
    ):
        super().__init__(
            system_id=system_id,
            system_type=system_type,
            topic=topic,
            bus=bus,
            health_port=health_port,
        )

    def _register_handlers(self):
        for action in self.ACTION_ROUTING:
            self.register_handler(action, self._handle_proxy)

    def _handle_proxy(self, message: Dict[str, Any]) -> Dict[str, Any]:
        action = message.get("action")
        topic = self.ACTION_ROUTING.get(action)

        if not topic:
            return {"error": f"no route for action: {action}"}

        response = self.bus.request(
            topic,
            {
                "action": action,
                "sender": self.system_id,
                "payload": message.get("payload", {}),
            },
            timeout=self.PROXY_TIMEOUT,
        )

        if response is None:
            return {"error": f"timeout waiting for {action}"}

        if response.get("success"):
            return response["payload"]

        return {"error": response.get("error", f"failed: {action}")}

    def get_status(self) -> Dict[str, Any]:
        status = super().get_status()
        status["routing"] = dict(self.ACTION_ROUTING)
        return status
