"""Unit тесты BaseGateway (моки, без брокера)."""
import pytest
from unittest.mock import MagicMock

from sdk.base_gateway import BaseGateway


class StubGateway(BaseGateway):
    ACTION_ROUTING = {
        "do_a": "components.comp_a",
        "do_b": "components.comp_b",
    }
    PROXY_TIMEOUT = 5.0


@pytest.fixture
def gateway_and_bus():
    bus = MagicMock()
    gw = StubGateway(
        system_id="test_gw",
        system_type="test",
        topic="systems.test",
        bus=bus,
    )
    return gw, bus


def test_handlers_registered(gateway_and_bus):
    gw, _ = gateway_and_bus
    assert "do_a" in gw._handlers
    assert "do_b" in gw._handlers
    assert "ping" in gw._handlers
    assert "get_status" in gw._handlers


def test_proxy_routes_to_correct_topic(gateway_and_bus):
    gw, bus = gateway_and_bus
    bus.request.return_value = {
        "success": True,
        "payload": {"result": "ok"},
    }

    message = {"action": "do_a", "sender": "ext", "payload": {"x": 1}}
    result = gw._handle_proxy(message)

    bus.request.assert_called_once_with(
        "components.comp_a",
        {"action": "do_a", "sender": "test_gw", "payload": {"x": 1}},
        timeout=5.0,
    )
    assert result == {"result": "ok"}


def test_proxy_routes_action_b(gateway_and_bus):
    gw, bus = gateway_and_bus
    bus.request.return_value = {
        "success": True,
        "payload": {"data": "from_b"},
    }

    message = {"action": "do_b", "sender": "ext", "payload": {}}
    result = gw._handle_proxy(message)

    bus.request.assert_called_once_with(
        "components.comp_b",
        {"action": "do_b", "sender": "test_gw", "payload": {}},
        timeout=5.0,
    )
    assert result == {"data": "from_b"}


def test_proxy_timeout_returns_error(gateway_and_bus):
    gw, bus = gateway_and_bus
    bus.request.return_value = None

    message = {"action": "do_a", "sender": "ext", "payload": {}}
    result = gw._handle_proxy(message)

    assert "error" in result
    assert "timeout" in result["error"]


def test_proxy_failure_returns_error(gateway_and_bus):
    gw, bus = gateway_and_bus
    bus.request.return_value = {
        "success": False,
        "error": "something broke",
    }

    message = {"action": "do_a", "sender": "ext", "payload": {}}
    result = gw._handle_proxy(message)

    assert result["error"] == "something broke"


def test_proxy_no_route_returns_error(gateway_and_bus):
    gw, _ = gateway_and_bus

    message = {"action": "unknown", "sender": "ext", "payload": {}}
    result = gw._handle_proxy(message)

    assert "error" in result
    assert "no route" in result["error"]


def test_get_status_includes_routing(gateway_and_bus):
    gw, _ = gateway_and_bus
    status = gw.get_status()

    assert status["routing"] == {
        "do_a": "components.comp_a",
        "do_b": "components.comp_b",
    }
    assert status["system_id"] == "test_gw"


def test_message_routing_sends_response(gateway_and_bus):
    gw, bus = gateway_and_bus
    bus.request.return_value = {
        "success": True,
        "payload": {"result": "ok"},
    }

    message = {
        "action": "do_a",
        "sender": "ext",
        "payload": {"x": 1},
        "reply_to": "replies.ext",
        "correlation_id": "corr123",
    }
    gw._handle_message(message)

    bus.publish.assert_called_once()
    call_args = bus.publish.call_args[0]
    assert call_args[0] == "replies.ext"
    response = call_args[1]
    assert response["success"] is True
    assert response["payload"] == {"result": "ok"}
    assert response["correlation_id"] == "corr123"
