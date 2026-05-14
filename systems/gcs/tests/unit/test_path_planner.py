import pytest
from datetime import datetime
from ...src.contracts import MissionStatus
from ...src.path_planner.src.route_generator import (
    expand_three_points_to_snake_path,
    expand_two_points_to_path,
)
from ...src.mission_store.topics import MissionStoreActions
from ...src.path_planner.src.path_planner import PathPlannerComponent
from ...src.path_planner.topics import ComponentTopics


@pytest.fixture
def component(mock_bus):
    return PathPlannerComponent(component_id="path-planner", bus=mock_bus)


def test_build_route_two_points_uses_local_generator(component):
    waypoints = [
        {"lat": 10.0, "lon": 20.0, "alt_m": 30.0},
        {"lat": 16.0, "lon": 26.0, "alt_m": 36.0},
    ]

    route = component._build_route(waypoints)
    expected = expand_two_points_to_path(waypoints)

    assert route == expected


def test_build_route_three_points_uses_local_snake_generator(component):
    waypoints = [
        {"lat": 55.750000, "lon": 37.610000, "alt_m": 60.0},
        {"lat": 55.749000, "lon": 37.611000, "alt_m": 60.0},
        {"lat": 55.752000, "lon": 37.616000, "alt_m": 80.0},
    ]

    route = component._build_route(waypoints)
    expected = expand_three_points_to_snake_path(waypoints)

    assert route == expected


def test_build_route_rejects_invalid_waypoints(component):
    with pytest.raises(ValueError):
        component._build_route([{"lat": "bad", "lon": 2.0}])

def test_build_route_rejects_unsupported_number_of_points(component):
    waypoints = [
        {"lat": 1.0, "lon": 2.0, "alt": 3.0},
    ]  # валидная точка, но количество = 1

    with pytest.raises(ValueError, match="either 2 or 3 route points"):
        component._build_route(waypoints)


def test_expand_two_points_to_path_rejects_invalid_point_count():
    with pytest.raises(ValueError, match="need exactly 2 seed points"):
        expand_two_points_to_path([{"lat": 1.0, "lon": 2.0, "alt_m": 3.0}])


def test_expand_three_points_to_snake_path_rejects_invalid_point_count():
    with pytest.raises(ValueError, match="need exactly 3 seed points"):
        expand_three_points_to_snake_path(
            [
                {"lat": 1.0, "lon": 2.0, "alt_m": 3.0},
                {"lat": 4.0, "lon": 5.0, "alt_m": 6.0},
            ]
        )


def test_handle_path_plan_saves_mission_and_returns_route(component, mock_bus):
    message = {
        "payload": {
            "mission_id": "m-plan",
            "task": {
                "waypoints": [
                    {"lat": 1.0, "lon": 2.0, "alt_m": 3.0},
                    {"lat": 4.0, "lon": 5.0, "alt_m": 6.0},
                ],
            },
        },
        "correlation_id": "corr-1",
    }

    result = component._handle_path_plan(message)

    expected_waypoints = expand_two_points_to_path(
        [
            {"lat": 1.0, "lon": 2.0, "alt_m": 3.0},
            {"lat": 4.0, "lon": 5.0, "alt_m": 6.0},
        ]
    )

    assert result == {
        "from": "path-planner",
        "mission_id": "m-plan",
        "waypoints": expected_waypoints,
    }

    # Корректность маршрута относительно текущей реализации (связка handler->builder)
    mock_bus.publish.assert_called_once()
    topic, saved_message = mock_bus.publish.call_args.args
    assert topic == ComponentTopics.MISSION_STORE

    assert saved_message["action"] == MissionStoreActions.SAVE_MISSION
    assert saved_message["sender"] == "path-planner"
    assert saved_message["correlation_id"] == "corr-1"

    mission = saved_message["payload"]["mission"]
    assert mission["mission_id"] == "m-plan"
    assert mission["waypoints"] == expected_waypoints
    assert mission["status"] == MissionStatus.CREATED
    assert mission["assigned_drone"] is None

    assert mission["created_at"] == mission["updated_at"]
    datetime.fromisoformat(mission["created_at"])  # должно парситься

def _assert_invalid(component, mock_bus, bad_message):
    assert component._handle_path_plan(bad_message) == {
        "from": "path-planner",
        "error": "failed to build route",
    }
    mock_bus.publish.assert_not_called()

def test_handle_path_plan_returns_error_for_invalid_task(component, mock_bus):
    _assert_invalid(component, mock_bus, {
        "payload": {
            "mission_id": "m-bad",
            "task": {"waypoints": [{"lat": 1.0}]},
        },
        "correlation_id": "corr-bad",
    })

def test_handle_path_plan_sets_timestamps_on_saved_mission(component, mock_bus):
    component._handle_path_plan(
        {
            "payload": {
                "mission_id": "m-time",
                "task": {
                    "waypoints": [
                        {"lat": 1.0, "lon": 2.0},
                        {"lat": 3.0, "lon": 4.0},
                    ],
                },
            },
            "correlation_id": "corr-time",
        }
    )

    mock_bus.publish.assert_called_once()
    saved_message = mock_bus.publish.call_args.args[1]
    assert saved_message["correlation_id"] == "corr-time"

    mission = saved_message["payload"]["mission"]
    assert mission["created_at"]
    assert mission["updated_at"]
    assert mission["created_at"] == mission["updated_at"]
    datetime.fromisoformat(mission["created_at"])

def test_handle_path_plan_raises_when_payload_missing(component, mock_bus):
    _assert_invalid(component, mock_bus, {})

def test_handle_path_plan_raises_when_task_missing(component, mock_bus):
    _assert_invalid(component, mock_bus, {"payload": {"mission_id": "m-1"}})

def test_handle_path_plan_raises_when_end_point_missing(component, mock_bus):
    
    _assert_invalid(component, mock_bus, {
        "payload": {"mission_id": "m-2", "task": {"start_point": {"lat": 1.0}}},
    })

def test_handle_path_plan_raises_when_coordinates_invalid(component, mock_bus):
    # для текущего формата: waypoints есть, но координаты невалидные
    _assert_invalid(component, mock_bus, {
        "payload": {
            "mission_id": "m-3",
            "task": {"waypoints": [{"lat": "bad", "lon": 2.0, "alt": 3.0}, {"lat": 4.0, "lon": 5.0, "alt": 6.0}]},
        }
    })
