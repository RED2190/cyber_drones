from unittest.mock import MagicMock

from ...src.gateway.src.gateway import GCSGateway
from ...src.gateway.topics import GatewayActions
from ...src.orchestrator.topics import ComponentTopics


def test_gateway_routes_task_submit_to_orchestrator():
    bus = MagicMock()
    gateway = GCSGateway(system_id="gcs", bus=bus)
    bus.request.return_value = {
        "success": True,
        "payload": {"mission_id": "m-1", "waypoints": [1, 2, 3]},
    }

    result = gateway._handle_proxy(
        {
            "action": GatewayActions.TASK_SUBMIT,
            "sender": "external",
            "payload": {"waypoints": [1, 2]},
        }
    )

    bus.request.assert_called_once_with(
        ComponentTopics.ORCHESTRATOR,
        {
            "action": GatewayActions.TASK_SUBMIT,
            "sender": "gcs",
            "payload": {"waypoints": [1, 2]},
        },
        timeout=10.0,
    )
    assert result["mission_id"] == "m-1"


def test_gateway_routes_task_start_to_orchestrator():
    bus = MagicMock()
    gateway = GCSGateway(system_id="gcs", bus=bus)
    bus.request.return_value = {
        "success": True,
        "payload": {"ok": True, "forwarded_action": "mission.start"},
    }

    result = gateway._handle_proxy(
        {
            "action": GatewayActions.TASK_START,
            "sender": "external",
            "payload": {"mission_id": "m-2", "drone_id": "dr-1"},
        }
    )

    bus.request.assert_called_once_with(
        ComponentTopics.ORCHESTRATOR,
        {
            "action": GatewayActions.TASK_START,
            "sender": "gcs",
            "payload": {"mission_id": "m-2", "drone_id": "dr-1"},
        },
        timeout=10.0,
    )
    assert result["ok"] is True


def test_gateway_timeout_returns_error():
    bus = MagicMock()
    gateway = GCSGateway(system_id="gcs", bus=bus)
    bus.request.return_value = None

    result = gateway._handle_proxy(
        {
            "action": GatewayActions.TASK_ASSIGN,
            "sender": "external",
            "payload": {"mission_id": "m-3", "drone_id": "dr-2"},
        }
    )

    assert "error" in result
