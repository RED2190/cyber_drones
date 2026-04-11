"""Тесты BaseSystem из SDK."""
import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, Any

from sdk.base_system import BaseSystem


class ConcreteSystem(BaseSystem):
    """Минимальная реализация для тестирования."""
    def _register_handlers(self):
        self.register_handler("echo", self._handle_echo)

    def _handle_echo(self, message: Dict[str, Any]) -> Dict[str, Any]:
        return {"echo": message.get("payload", {}).get("data")}


@pytest.fixture
def bus():
    return MagicMock()


@pytest.fixture
def system(bus):
    with patch('sdk.base_system.threading'):
        return ConcreteSystem(
            system_id="test_sys",
            system_type="test",
            topic="systems.test",
            bus=bus,
            health_port=None
        )


def test_handlers_registered(system):
    assert "echo" in system._handlers
    assert "ping" in system._handlers
    assert "get_status" in system._handlers


def test_handle_ping(system):
    result = system._handle_ping({})
    assert result["pong"] is True
    assert result["system_id"] == "test_sys"


def test_get_status(system):
    status = system.get_status()
    assert status["system_id"] == "test_sys"
    assert status["system_type"] == "test"
    assert "echo" in status["handlers"]


def test_handle_echo(system):
    msg = {"action": "echo", "sender": "x", "payload": {"data": "hello"}}
    result = system._handle_echo(msg)
    assert result["echo"] == "hello"


def test_message_routing_with_reply(system, bus):
    msg = {
        "action": "echo",
        "sender": "client",
        "payload": {"data": "test"},
        "reply_to": "replies.client",
        "correlation_id": "c1",
    }
    system._handle_message(msg)
    bus.publish.assert_called_once()
    call_args = bus.publish.call_args[0]
    assert call_args[0] == "replies.client"
    assert call_args[1]["success"] is True
