"""
Базовый класс для компонентов, использующих SystemBus.

Аналогичен BaseSystem, но без health check и run_forever.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Optional

from systems.agrodron.src.broker.system_bus import SystemBus
from systems.agrodron.src.sdk.messages import create_response

logger = logging.getLogger(__name__)


class BaseComponent(ABC):
    """
    Абстрактный базовый класс для компонентов дрона.

    Компонент:
    - Подключается к SystemBus (единая шина с системами)
    - Подписывается на свой топик (components.{component_type})
    - Обрабатывает сообщения через маршрутизацию по action
    - Отвечает через reply_to (request/response) или publish
    """

    def __init__(
        self,
        component_id: str,
        component_type: str,
        topic: str,
        bus: SystemBus,
    ):
        self.component_id = component_id
        self.component_type = component_type
        self.topic = topic
        self.bus = bus

        self._handlers: Dict[str, Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]] = {}
        self._running = False

        self._setup_handlers()
        self._register_handlers()

    def _setup_handlers(self):
        """Базовые обработчики."""
        self.register_handler("ping", self._handle_ping)
        self.register_handler("get_status", self._handle_get_status)

    @abstractmethod
    def _register_handlers(self):
        """Регистрирует обработчики конкретного компонента."""
        pass

    def register_handler(
        self,
        action: str,
        handler: Callable[[Dict[str, Any]], Optional[Dict[str, Any]]],
    ):
        """Регистрирует обработчик для action."""
        self._handlers[action] = handler

    def _handle_message(self, message: Dict[str, Any]):
        """Маршрутизация входящего сообщения по action."""
        action = message.get("action")
        reply_to = message.get("reply_to")
        if not action:
            print(f"[{self.component_id}] Message without action: {message}")
            return

        handler = self._handlers.get(action)
        if not handler:
            print(f"[{self.component_id}] Unknown action: {action}")
            if reply_to:
                self.bus.respond(message, {"error": f"Unknown action: {action}"}, action="error")
            return

        if reply_to:
            logger.info(
                "[%s] request action=%s reply_to=%s",
                self.component_id, action, reply_to,
            )
        try:
            result = handler(message)
            if reply_to and result is not None:
                response = create_response(
                    correlation_id=message.get("correlation_id"),
                    payload=result,
                    sender=self.topic,
                    success=True,
                )
                self.bus.publish(reply_to, response)
                logger.info("[%s] response sent to %s", self.component_id, reply_to)
        except Exception as e:
            print(f"[{self.component_id}] Error handling {action}: {e}")
            if reply_to:
                response = create_response(
                    correlation_id=message.get("correlation_id"),
                    payload={},
                    sender=self.topic,
                    success=False,
                    error=str(e),
                )
                self.bus.publish(reply_to, response)
                logger.info("[%s] error response sent to %s", self.component_id, reply_to)

    def _handle_ping(self, message: Dict[str, Any]) -> Dict[str, Any]:
        return {"pong": True, "component_id": self.component_id}

    def _handle_get_status(self, message: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "component_type": self.component_type,
            "topic": self.topic,
            "running": self._running,
            "handlers": list(self._handlers.keys()),
        }

    def start(self):
        """Подписывается на топик и запускает шину."""
        self.bus.start()
        self.bus.subscribe(self.topic, self._handle_message)
        self._running = True
        print(f"[{self.component_id}] Started. Listening on topic: {self.topic}")
        self._log_component_started()

    def _log_component_started(self) -> None:
        """Запись в журнал при старте (через МБ; у journal — локальная запись, см. JournalComponent)."""
        if self.component_type == "journal":
            return
        try:
            from systems.agrodron.src.sdk.journal_log import publish_journal_event

            publish_journal_event(
                self.bus,
                self.topic,
                "COMPONENT_STARTED",
                source=self.component_type,
                details={
                    "component_id": self.component_id,
                    "topic": self.topic,
                },
            )
        except Exception as exc:
            logger.debug("[%s] journal startup log skipped: %s", self.component_id, exc)

    def stop(self):
        """Отписывается и останавливает шину."""
        self._running = False
        self.bus.unsubscribe(self.topic)
        self.bus.stop()
        print(f"[{self.component_id}] Stopped")
