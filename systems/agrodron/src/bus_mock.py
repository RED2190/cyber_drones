"""Общий мок SystemBus для unit-тестов компонентов."""
import asyncio
from typing import Any, Dict, Callable, Optional

from broker.system_bus import SystemBus


class MockSystemBus(SystemBus):
    """Реализация SystemBus для тестов: все методы — заглушки, publish пишет в список."""

    def __init__(self):
        self.published: list = []

    def publish(self, topic: str, message: Dict[str, Any]) -> bool:
        self.published.append((topic, message))
        return True

    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> bool:
        return True

    def unsubscribe(self, topic: str) -> bool:
        return True

    def request(
        self,
        topic: str,
        message: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Optional[Dict[str, Any]]:
        self.published.append((topic, message))
        return None

    def request_async(
        self,
        topic: str,
        message: Dict[str, Any],
        timeout: float = 30.0,
    ) -> asyncio.Future[Optional[Dict[str, Any]]]:
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
