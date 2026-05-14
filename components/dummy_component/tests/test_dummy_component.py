"""Unit тесты DummyComponent (моки, без брокера)."""
import pytest
from unittest.mock import MagicMock

from components.dummy_component.src.dummy_component import DummyComponent


@pytest.fixture
def bus():
    return MagicMock()


@pytest.fixture
def component(bus):
    return DummyComponent(
        component_id="test_component",
        name="TestDummy",
        bus=bus,
    )


def test_subscribe_on_start(component, bus):
    component.start()
    bus.subscribe.assert_called()


def test_echo(component):
    message = {"action": "echo", "sender": "test", "payload": {"message": "hello"}}
    result = component._handle_echo(message)
    assert result["echo"] == {"message": "hello"}
    assert result["from"] == "test_component"


def test_increment(component):
    assert component._state["counter"] == 0
    message = {"action": "increment", "sender": "test", "payload": {"value": 5}}
    result = component._handle_increment(message)
    assert component._state["counter"] == 5
    assert result["counter"] == 5


def test_get_state(component):
    component._state["counter"] = 42
    message = {"action": "get_state", "sender": "test", "payload": {}}
    result = component._handle_get_state(message)
    assert result["counter"] == 42


def test_message_routing(component, bus):
    message = {
        "action": "echo",
        "sender": "test",
        "payload": {"data": "ping"},
        "reply_to": "replies.test",
        "correlation_id": "abc123",
    }
    component._handle_message(message)
    bus.publish.assert_called_once()
