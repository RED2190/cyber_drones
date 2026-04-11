import pytest

from sdk.wpl_generator import expand_two_points_to_path
from sdk.wpl_generator_2 import expand_three_points_to_snake_path
from systems.gcs.src.contracts import MissionStatus
from systems.gcs.src.path_planner.src.path_planner import PathPlannerComponent
from systems.gcs.src.path_planner.topics import ComponentTopics, PathPlannerActions


@pytest.fixture
def component(mock_bus):
    return PathPlannerComponent(component_id="path-planner", bus=mock_bus)


def test_build_route_two_points_uses_sdk_generator(component):
    waypoints = [
        {"lat": 10.0, "lon": 20.0, "alt": 30.0},
        {"lat": 16.0, "lon": 26.0, "alt": 36.0},
    ]

    route = component._build_route(waypoints)
    expected = expand_two_points_to_path(waypoints)

    assert route == expected


def test_build_route_three_points_uses_snake_generator(component):
    waypoints = [
        {"lat": 55.750000, "lon": 37.610000, "alt": 60.0},
        {"lat": 55.749000, "lon": 37.611000, "alt": 60.0},
        {"lat": 55.752000, "lon": 37.616000, "alt": 80.0},
    ]

    route = component._build_route(waypoints)
    expected = expand_three_points_to_snake_path(waypoints)

    assert route == expected


def test_build_route_rejects_invalid_waypoints(component):
    with pytest.raises(ValueError):
        component._build_route([{"lat": "bad", "lon": 2.0}])


def test_handle_path_plan_saves_mission_and_returns_route(component, mock_bus):
    message = {
        "payload": {
            "mission_id": "m-plan",
            "task": {
                "waypoints": [
                    {"lat": 1.0, "lon": 2.0, "alt": 3.0},
                    {"lat": 4.0, "lon": 5.0, "alt": 6.0},
                ],
            },
        },
        "correlation_id": "corr-1",
    }

    result = component._handle_path_plan(message)

    expected_waypoints = component._build_route(
        [
            {"lat": 1.0, "lon": 2.0, "alt": 3.0},
            {"lat": 4.0, "lon": 5.0, "alt": 6.0},
        ]
    )
    assert result["mission_id"] == "m-plan"
    assert result["waypoints"] == expected_waypoints
    assert mock_bus.publish.call_args.args[0] == ComponentTopics.GCS_MISSION_STORE
    saved_message = mock_bus.publish.call_args.args[1]
    assert saved_message["action"] == "store.save_mission"
    assert saved_message["sender"] == "path-planner"
    assert saved_message["payload"]["mission"]["status"] == MissionStatus.CREATED
    assert saved_message["correlation_id"] == "corr-1"


def test_handle_path_plan_returns_error_for_invalid_task(component, mock_bus):
    result = component._handle_path_plan(
        {
            "payload": {
                "mission_id": "m-bad",
                "task": {"waypoints": [{"lat": 1.0}]},
            },
            "correlation_id": "corr-bad",
        }
    )

    assert result == {"from": "path-planner", "error": "failed to build route"}
    mock_bus.publish.assert_not_called()


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

    saved_mission = mock_bus.publish.call_args.args[1]["payload"]["mission"]
    assert saved_mission["created_at"]
    assert saved_mission["updated_at"]
    assert saved_mission["assigned_drone"] is None
