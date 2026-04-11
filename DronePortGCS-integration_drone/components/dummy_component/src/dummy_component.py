"""
DummyComponent - шаблон для создания новых компонентов.

Копируй эту папку и адаптируй под свои нужды.
"""
from typing import Dict, Any

from sdk.base_component import BaseComponent
from broker.src.system_bus import SystemBus


class DummyComponent(BaseComponent):

    def __init__(
        self,
        component_id: str,
        name: str,
        bus: SystemBus,
        topic: str = "components.dummy_component",
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

    def _handle_echo(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {})
        return {"echo": payload, "from": self.component_id}

    def _handle_increment(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {})
        self._state["counter"] += payload.get("value", 1)
        return {"counter": self._state["counter"], "from": self.component_id}

    def _handle_get_state(self, message: Dict[str, Any]) -> Dict[str, Any]:
        return {**self._state, "from": self.component_id}
