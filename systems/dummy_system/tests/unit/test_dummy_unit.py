"""Unit тесты для компонентов dummy_system (моки, без брокера)."""
import pytest
from unittest.mock import MagicMock

from systems.dummy_system.src.dummy_component_a.src.dummy_component import DummyComponent
from systems.dummy_system.src.dummy_component_b.src.dummy_component import DummyComponent as DummyComponentB
from systems.dummy_system.src.gateway.src.gateway import DummyGateway


@pytest.fixture
def component_and_bus():
    mock_bus = MagicMock()
    component = DummyComponent(
        component_id="test_component",
        name="TestDummy",
        bus=mock_bus,
    )
    return component, mock_bus


def test_dummy_component_increment(component_and_bus):
    component, bus = component_and_bus
    assert component._state["counter"] == 0
    message = {
        "action": "increment",
        "sender": "test_client",
        "payload": {"value": 5},
    }
    result = component._handle_increment(message)
    assert component._state["counter"] == 5
    assert result["counter"] == 5


def test_dummy_component_echo(component_and_bus):
    component, bus = component_and_bus
    message = {
        "action": "echo",
        "sender": "test_client",
        "payload": {"message": "hello"},
    }
    result = component._handle_echo(message)
    assert result["echo"] == {"message": "hello"}
    assert result["from"] == "test_component"


def test_dummy_component_get_state(component_and_bus):
    component, bus = component_and_bus
    component._state["counter"] = 42
    message = {"action": "get_state", "sender": "test_client", "payload": {}}
    result = component._handle_get_state(message)
    assert result["counter"] == 42
    assert result["from"] == "test_component"


def test_dummy_component_message_routing(component_and_bus):
    component, bus = component_and_bus
    message = {
        "action": "echo",
        "sender": "test_client",
        "payload": {"data": "ping"},
        "reply_to": "replies.test",
        "correlation_id": "abc123",
    }
    component._handle_message(message)
    bus.publish.assert_called_once()


def test_dummy_component_subscribe_on_start(component_and_bus):
    component, bus = component_and_bus
    component.start()
    bus.subscribe.assert_called()


@pytest.fixture
def component_b_and_bus():
    mock_bus = MagicMock()
    component = DummyComponentB(
        component_id="dummy_component_b",
        name="ComponentB",
        bus=mock_bus,
        topic="components.dummy_component_b",
    )
    return component, mock_bus


def test_component_b_get_data(component_b_and_bus):
    """B обрабатывает get_data и возвращает данные."""
    component, _ = component_b_and_bus
    message = {"action": "get_data", "sender": "a", "payload": {"query": "test"}}
    result = component._handle_get_data(message)
    assert result["data"] == "response_for_test"
    assert result["source"] == "dummy_component_b"


def test_component_a_ask_b_relays_b_response(component_and_bus):
    """A отправляет ask_b в B, получает ответ и возвращает его."""
    component, bus = component_and_bus
    bus.request.return_value = {
        "success": True,
        "payload": {"data": "from_b", "source": "dummy_component_b"},
    }
    message = {"action": "ask_b", "sender": "test", "payload": {"query": "x"}}
    result = component._handle_ask_b(message)
    assert result["b_response"]["data"] == "from_b"
    assert result["relayed_by"] == "test_component"
    bus.request.assert_called_once()


# --- Gateway tests ---

@pytest.fixture
def gateway_and_bus():
    mock_bus = MagicMock()
    gw = DummyGateway(system_id="test_gateway", bus=mock_bus)
    return gw, mock_bus


def test_gateway_routes_echo_to_component_a(gateway_and_bus):
    """Gateway проксирует echo в компонент A."""
    gw, bus = gateway_and_bus
    bus.request.return_value = {
        "success": True,
        "payload": {"echo": {"msg": "hi"}, "from": "dummy_component_a"},
    }

    message = {"action": "echo", "sender": "external", "payload": {"msg": "hi"}}
    result = gw._handle_proxy(message)

    bus.request.assert_called_once_with(
        "components.dummy_component_a",
        {"action": "echo", "sender": "test_gateway", "payload": {"msg": "hi"}},
        timeout=10.0,
    )
    assert result["echo"] == {"msg": "hi"}


def test_gateway_routes_get_data_to_component_b(gateway_and_bus):
    """Gateway проксирует get_data в компонент B."""
    gw, bus = gateway_and_bus
    bus.request.return_value = {
        "success": True,
        "payload": {"data": "response_for_test", "source": "dummy_component_b"},
    }

    message = {"action": "get_data", "sender": "external", "payload": {"query": "test"}}
    result = gw._handle_proxy(message)

    bus.request.assert_called_once_with(
        "components.dummy_component_b",
        {"action": "get_data", "sender": "test_gateway", "payload": {"query": "test"}},
        timeout=10.0,
    )
    assert result["data"] == "response_for_test"


def test_gateway_timeout_returns_error(gateway_and_bus):
    """Gateway возвращает ошибку при таймауте компонента."""
    gw, bus = gateway_and_bus
    bus.request.return_value = None

    message = {"action": "echo", "sender": "external", "payload": {}}
    result = gw._handle_proxy(message)

    assert "error" in result
