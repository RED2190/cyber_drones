from types import SimpleNamespace

import pytest

from systems.gcs.src.orchestrator.src import orchestrator as orchestrator_module
from systems.gcs.src.orchestrator.src.orchestrator import OrchestratorComponent
from systems.gcs.src.orchestrator.topics import ComponentTopics, OrchestratorActions
from systems.gcs.src.path_planner.topics import PathPlannerActions
from systems.gcs.src.mission_converter.topics import MissionActions
from systems.gcs.src.drone_manager.topics import DroneManagerActions


@pytest.fixture
def component(mock_bus):
    return OrchestratorComponent(component_id="orchestrator", bus=mock_bus)

def test_handle_task_submit_returns_route_when_planner_succeeds(component, mock_bus, monkeypatch):
    monkeypatch.setattr(orchestrator_module, "uuid4", lambda: SimpleNamespace(hex="abcdef1234567890"))
    mock_bus.request.return_value = {
        "success": True,
        "payload": {
            "waypoints": [1, 2, 3, 4],
        },
    }

    result = component._handle_task_submit({"payload": {"type": "delivery"}, "correlation_id": "corr-10"})

    assert result == {
        "from": "orchestrator",
        "mission_id": "m-abcdef123456",
        "waypoints": [1, 2, 3, 4],
    }
    mock_bus.request.assert_called_once_with(
        ComponentTopics.GCS_PATH_PLANNER,
        {
            "action": PathPlannerActions.PATH_PLAN,
            "sender": "orchestrator",
            "payload": {"mission_id": "m-abcdef123456", "task": {"type": "delivery"}},
            "correlation_id": "corr-10",
        },
        timeout=10.0,
    )


def test_handle_task_submit_returns_error_when_planner_fails(component, mock_bus):
    mock_bus.request.return_value = {"success": False}

    result = component._handle_task_submit({"payload": {"type": "delivery"}, "correlation_id": "corr-11"})

    assert result == {"from": "orchestrator", "error": "failed to build route"}


def test_handle_task_submit_returns_error_for_short_route(component, mock_bus):
    mock_bus.request.return_value = {
        "success": True,
        "payload": {"waypoints": [1, 2, 3]},
    }

    result = component._handle_task_submit({"payload": {"type": "delivery"}, "correlation_id": "corr-12"})

    assert result == {"from": "orchestrator", "error": "failed to build route"}


def test_handle_task_assign_publishes_upload_when_converter_returns_wpl(component, mock_bus):
    mock_bus.request.return_value = {
        "success": True,
        "payload": {"mission": {"wpl": "QGC WPL 110"}},
    }

    component._handle_task_assign(
        {
            "payload": {"mission_id": "m-assign", "drone_id": "dr-7"},
            "correlation_id": "corr-12",
        }
    )

    mock_bus.request.assert_called_once_with(
        ComponentTopics.GCS_MISSION_CONVERTER,
        {
            "action": MissionActions.MISSION_PREPARE,
            "sender": "orchestrator",
            "payload": {"mission_id": "m-assign"},
            "correlation_id": "corr-12",
        },
        timeout=30.0,
    )
    mock_bus.publish.assert_called_once_with(
        ComponentTopics.GCS_DRONE_MANAGER,
        {
            "action": DroneManagerActions.MISSION_UPLOAD,
            "sender": "orchestrator",
            "payload": {"mission_id": "m-assign", "drone_id": "dr-7", "wpl": "QGC WPL 110"},
            "correlation_id": "corr-12",
        },
    )


def test_handle_task_assign_skips_publish_without_wpl(component, mock_bus):
    mock_bus.request.return_value = {
        "success": True,
        "payload": {"mission": {}},
    }

    assert component._handle_task_assign(
        {"payload": {"mission_id": "m-assign", "drone_id": "dr-7"}, "correlation_id": "corr-14"}
    ) is None
    mock_bus.publish.assert_not_called()


def test_handle_task_start_publishes_start_command(component, mock_bus):
    component._handle_task_start(
        {
            "payload": {"mission_id": "m-start", "drone_id": "dr-8"},
            "correlation_id": "corr-13",
        }
    )

    mock_bus.publish.assert_called_once_with(
        ComponentTopics.GCS_DRONE_MANAGER,
        {
            "action": DroneManagerActions.MISSION_START,
            "sender": "orchestrator",
            "payload": {"mission_id": "m-start", "drone_id": "dr-8"},
            "correlation_id": "corr-13",
        },
    )
