from types import SimpleNamespace

import pytest

from ...src.orchestrator.src import orchestrator as orchestrator_module
from ...src.orchestrator.src.orchestrator import OrchestratorComponent
from ...src.orchestrator.topics import ComponentTopics, OrchestratorActions
from ...src.path_planner.topics import PathPlannerActions
from ...src.mission_converter.topics import MissionActions
from ...src.drone_manager.topics import DroneManagerActions


@pytest.fixture
def component(mock_bus):
    return OrchestratorComponent(component_id="orchestrator", bus=mock_bus)

def test_registers_orchestrator_handlers(component):
    """Проверяет, что orchestrator регистрирует свои action-handlers при инициализации."""
    assert OrchestratorActions.TASK_SUBMIT in component._handlers
    assert OrchestratorActions.TASK_ASSIGN in component._handlers
    assert OrchestratorActions.TASK_START in component._handlers

def test_handle_task_submit_returns_route_when_planner_succeeds(component, mock_bus, monkeypatch):
    """Если PathPlanner вернул success=True и достаточно waypoints, orchestrator возвращает mission_id+waypoints и прокидывает correlation_id в request."""
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
        ComponentTopics.PATH_PLANNER,
        {
            "action": PathPlannerActions.PATH_PLAN,
            "sender": "orchestrator",
            "payload": {"mission_id": "m-abcdef123456", "task": {"type": "delivery"}},
            "correlation_id": "corr-10",
        },
        timeout=10.0,
    )


def test_handle_task_submit_returns_error_when_planner_fails(component, mock_bus, monkeypatch):
    """Если PathPlanner вернул success=False, orchestrator возвращает ошибку."""
    monkeypatch.setattr(orchestrator_module, "uuid4", lambda: SimpleNamespace(hex="abcdef1234567890"))
    mock_bus.request.return_value = {"success": False}

    result = component._handle_task_submit({"payload": {"type": "delivery"}, "correlation_id": "corr-11"})

    assert result == {"from": "orchestrator", "error": "failed to build route"}


def test_handle_task_submit_returns_error_for_short_route(component, mock_bus, monkeypatch):
    """Если PathPlanner вернул слишком короткий маршрут (<4), orchestrator возвращает ошибку."""
    monkeypatch.setattr(orchestrator_module, "uuid4", lambda: SimpleNamespace(hex="abcdef1234567890"))
    mock_bus.request.return_value = {
        "success": True,
        "payload": {"waypoints": [1, 2, 3]},
    }

    result = component._handle_task_submit({"payload": {"type": "delivery"}, "correlation_id": "corr-12"})

    assert result == {"from": "orchestrator", "error": "failed to build route"}

def test_handle_task_submit_returns_error_when_planner_times_out(component, mock_bus, monkeypatch):
    """Если PathPlanner недоступен/таймаут (request вернул None), orchestrator возвращает ошибку."""
    monkeypatch.setattr(orchestrator_module, "uuid4", lambda: SimpleNamespace(hex="abcdef1234567890"))
    mock_bus.request.return_value = None

    result = component._handle_task_submit({"payload": {"type": "delivery"}, "correlation_id": "corr-timeout"})

    assert result == {"from": "orchestrator", "error": "failed to build route"}


def test_handle_task_submit_does_not_forward_correlation_id_when_missing(component, mock_bus, monkeypatch):
    """Если correlation_id нет во входном сообщении, orchestrator не добавляет его в request к PathPlanner."""
    monkeypatch.setattr(orchestrator_module, "uuid4", lambda: SimpleNamespace(hex="abcdef1234567890"))
    mock_bus.request.return_value = {"success": True, "payload": {"waypoints": [1, 2, 3, 4]}}

    component._handle_task_submit({"payload": {"type": "delivery"}})

    # У mission_id детерминированное значение, так что можно проверять полный message
    mock_bus.request.assert_called_once()
    topic, planned_message = mock_bus.request.call_args.args
    assert topic == ComponentTopics.PATH_PLANNER
    assert planned_message == {
        "action": PathPlannerActions.PATH_PLAN,
        "sender": "orchestrator",
        "payload": {"mission_id": "m-abcdef123456", "task": {"type": "delivery"}},
    }
    assert mock_bus.request.call_args.kwargs["timeout"] == 10.0

def test_handle_task_submit_returns_error_when_waypoints_not_list(component, mock_bus, monkeypatch):
    """Если PathPlanner вернул waypoints неправильного типа, orchestrator возвращает ошибку."""
    monkeypatch.setattr(orchestrator_module, "uuid4", lambda: SimpleNamespace(hex="abcdef1234567890"))
    mock_bus.request.return_value = {"success": True, "payload": {"waypoints": "not-a-list"}}

    result = component._handle_task_submit({"payload": {"type": "delivery"}, "correlation_id": "corr-x"})

    assert result == {"from": "orchestrator", "error": "failed to build route"}


def test_handle_task_assign_publishes_upload_when_converter_returns_wpl(component, mock_bus):
    """Если MissionConverter вернул WPL, orchestrator публикует mission.upload в DroneManager."""
    mock_bus.request.return_value = {
        "success": True,
        "payload": {"mission": {"wpl": "QGC WPL 110"}},
    }

    result = component._handle_task_assign(
        {
            "payload": {"mission_id": "m-assign", "drone_id": "dr-7"},
            "correlation_id": "corr-12",
        }
    )

    assert result == {
        "ok": True,
        "mission_id": "m-assign",
        "drone_id": "dr-7",
        "forwarded_action": DroneManagerActions.MISSION_UPLOAD,
    }

    mock_bus.request.assert_called_once_with(
        ComponentTopics.MISSION_CONVERTER,
        {
            "action": MissionActions.MISSION_PREPARE,
            "sender": "orchestrator",
            "payload": {"mission_id": "m-assign"},
            "correlation_id": "corr-12",
        },
        timeout=30.0,
    )
    mock_bus.publish.assert_called_once_with(
        ComponentTopics.DRONE_MANAGER,
        {
            "action": DroneManagerActions.MISSION_UPLOAD,
            "sender": "orchestrator",
            "payload": {"mission_id": "m-assign", "drone_id": "dr-7", "wpl": "QGC WPL 110"},
            "correlation_id": "corr-12",
        },
    )


def test_handle_task_assign_skips_publish_without_wpl(component, mock_bus):
    """Если MissionConverter вернул success=True, но wpl отсутствует, orchestrator ничего не публикует."""
    mock_bus.request.return_value = {
        "success": True,
        "payload": {"mission": {}},
    }

    assert component._handle_task_assign(
        {"payload": {"mission_id": "m-assign", "drone_id": "dr-7"}, "correlation_id": "corr-14"}
    ) == {
        "ok": False,
        "mission_id": "m-assign",
        "drone_id": "dr-7",
        "error": "mission_prepare_failed",
    }
    mock_bus.publish.assert_not_called()

def test_handle_task_assign_skips_publish_when_converter_fails(component, mock_bus):
    """Если MissionConverter вернул success=False, orchestrator ничего не публикует."""
    mock_bus.request.return_value = {"success": False, "payload": {}}

    assert component._handle_task_assign(
        {"payload": {"mission_id": "m-assign", "drone_id": "dr-7"}, "correlation_id": "corr-15"}
    ) == {
        "ok": False,
        "mission_id": "m-assign",
        "drone_id": "dr-7",
        "error": "mission_prepare_failed",
    }
    mock_bus.publish.assert_not_called()


def test_handle_task_assign_skips_publish_on_timeout(component, mock_bus):
    """Если MissionConverter недоступен/таймаут (request вернул None), orchestrator ничего не публикует."""
    mock_bus.request.return_value = None

    assert component._handle_task_assign(
        {"payload": {"mission_id": "m-assign", "drone_id": "dr-7"}, "correlation_id": "corr-16"}
    ) == {
        "ok": False,
        "mission_id": "m-assign",
        "drone_id": "dr-7",
        "error": "mission_prepare_failed",
    }
    mock_bus.publish.assert_not_called()

def test_handle_task_start_publishes_start_command(component, mock_bus):
    result = component._handle_task_start(
        {
            "payload": {"mission_id": "m-start", "drone_id": "dr-8"},
            "correlation_id": "corr-13",
        }
    )

    assert result == {
        "ok": True,
        "mission_id": "m-start",
        "drone_id": "dr-8",
        "forwarded_action": DroneManagerActions.MISSION_START,
    }

    mock_bus.publish.assert_called_once_with(
        ComponentTopics.DRONE_MANAGER,
        {
            "action": DroneManagerActions.MISSION_START,
            "sender": "orchestrator",
            "payload": {"mission_id": "m-start", "drone_id": "dr-8"},
            "correlation_id": "corr-13",
        },
    )

def test_handle_task_start_omits_correlation_id_when_missing(component, mock_bus):
    """Если correlation_id нет, orchestrator не добавляет его в publish message."""
    assert component._handle_task_start({"payload": {"mission_id": "m-start", "drone_id": "dr-8"}}) == {
        "ok": True,
        "mission_id": "m-start",
        "drone_id": "dr-8",
        "forwarded_action": DroneManagerActions.MISSION_START,
    }

    mock_bus.publish.assert_called_once()
    _, publish_message = mock_bus.publish.call_args.args
    assert "correlation_id" not in publish_message
