"""
DummyComponent — копия компонента для работы в составе dummy_system.
"""
from typing import Dict, Any

from sdk.base_component import BaseComponent
from broker.system_bus import SystemBus

from systems.dummy_system.src.dummy_component_a.topics import (
    ComponentTopics,
    DummyComponentActions,
)


class DummyComponent(BaseComponent):

    def __init__(
        self,
        component_id: str,
        name: str,
        bus: SystemBus,
        topic: str = "components.dummy_component_a",
    ):
        self.name = name
        self._state = {"counter": 0}
        super().__init__(
            component_id=component_id,
            component_type="dummy_component",
            topic=topic,
            bus=bus,
        )
        print(f"DummyComponent '{name}' initialized")

    def _register_handlers(self):
        self.register_handler("echo", self._handle_echo)
        self.register_handler("increment", self._handle_increment)
        self.register_handler("get_state", self._handle_get_state)
        self.register_handler(DummyComponentActions.ASK_B, self._handle_ask_b)

    def _handle_echo(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {})
        return {"echo": payload, "from": self.component_id}

    def _handle_increment(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {})
        self._state["counter"] += payload.get("value", 1)
        return {"counter": self._state["counter"], "from": self.component_id}

    def _handle_get_state(self, message: Dict[str, Any]) -> Dict[str, Any]:
        return {**self._state, "from": self.component_id}

    def _handle_ask_b(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Отправляет запрос в компонент B и возвращает его ответ."""
        payload = message.get("payload", {})
        query = payload.get("query", "")
        response = self.bus.request(
            ComponentTopics.DUMMY_COMPONENT_B,
            {
                "action": DummyComponentActions.GET_DATA,
                "sender": self.component_id,
                "payload": {"query": query},
            },
            timeout=10.0,
        )
        if response and response.get("success"):
            return {"b_response": response["payload"], "relayed_by": self.component_id}
        return {"error": "no response from B", "from": self.component_id}
