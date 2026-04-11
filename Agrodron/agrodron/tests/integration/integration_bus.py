"""In-process bus for integration tests: routes messages between components."""
import threading
from typing import Any, Callable, Dict, Optional

from broker.system_bus import SystemBus


class IntegrationBus(SystemBus):
    """
    Routes publish/request between components registered on topics.
    All communication is synchronous and in-process.

    For request(): directly invokes the component's handler for the given action
    and returns the result (bypasses _handle_message / respond flow).
    """

    def __init__(self):
        self._components: Dict[str, Any] = {}
        self._raw_handlers: Dict[str, Callable] = {}
        self._lock = threading.Lock()
        self.published: list = []

    def register_component(self, topic: str, component) -> None:
        """Register a BaseComponent. request() will call its handler directly."""
        with self._lock:
            self._components[topic] = component

    def register_topic_handler(self, topic: str, handler: Callable) -> None:
        """Register a raw callable (for external system stubs etc.)."""
        with self._lock:
            self._raw_handlers[topic] = handler

    def publish(self, topic: str, message: Dict[str, Any]) -> bool:
        self.published.append((topic, dict(message)))
        comp = self._components.get(topic)
        if comp:
            try:
                comp._handle_message(message)
            except Exception:
                pass
            return True
        handler = self._raw_handlers.get(topic)
        if handler:
            try:
                handler(message)
            except Exception:
                pass
        return True

    def subscribe(self, topic: str, callback: Callable) -> bool:
        return True

    def unsubscribe(self, topic: str) -> bool:
        return True

    def request(self, topic: str, message: Dict[str, Any], timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        self.published.append((topic, dict(message)))
        comp = self._components.get(topic)
        if comp:
            action = message.get("action", "")
            handler = comp._handlers.get(action)
            if handler:
                try:
                    return handler(message)
                except Exception:
                    return None
            return None
        raw = self._raw_handlers.get(topic)
        if raw:
            try:
                return raw(message)
            except Exception:
                return None
        return None

    async def request_async(self, topic: str, message: Dict[str, Any], timeout: float = 30.0):
        return self.request(topic, message, timeout)

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass
