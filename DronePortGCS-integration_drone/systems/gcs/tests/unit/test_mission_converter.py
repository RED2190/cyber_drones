import pytest

from sdk.wpl_generator_2 import points_to_wpl as points_to_wpl_v2
from systems.gcs.src.mission_converter.src.mission_converter import MissionConverterComponent
from systems.gcs.src.mission_store.topics import ComponentTopics, MissionStoreActions


@pytest.fixture
def component(mock_bus):
    return MissionConverterComponent(component_id="mission-converter", bus=mock_bus)


def test_to_wpl_serializes_explicit_waypoints_via_sdk(component):
    points = [
        {"lat": 55.1, "lon": 37.2, "alt": 100},
        {"lat": 55.2, "lon": 37.3, "alt": 110},
        {"lat": 55.3, "lon": 37.4, "alt": 120},
        {"lat": 55.4, "lon": 37.5, "alt": 130},
    ]

    result = points_to_wpl_v2(points)
    expected = points_to_wpl_v2(points)

    assert result == expected


def test_handle_mission_prepare_returns_wpl(component, mock_bus):
    mission = {
        "waypoints": [
            {"lat": 10.0, "lon": 20.0, "alt": 30.0},
            {"lat": 11.0, "lon": 21.0, "alt": 31.0},
        ]
    }
    mock_bus.request.return_value = {
        "success": True,
        "payload": {"mission": mission},
    }

    result = component._handle_mission_prepare({"payload": {"mission_id": "m-1"}, "correlation_id": "corr-1"})

    expected_wpl = points_to_wpl_v2(mission["waypoints"])
    assert result == {
        "mission": {
            "mission_id": "m-1",
            "wpl": expected_wpl,
        },
        "from": "mission-converter",
    }
    mock_bus.request.assert_called_once_with(
        ComponentTopics.GCS_MISSION_STORE,
        {
            "action": MissionStoreActions.GET_MISSION,
            "sender": "mission-converter",
            "payload": {"mission_id": "m-1"},
            "correlation_id": "corr-1",
        },
        timeout=10.0,
    )


def test_handle_mission_prepare_returns_error_when_store_unavailable(component, mock_bus):
    mock_bus.request.return_value = None

    result = component._handle_mission_prepare({"payload": {"mission_id": "m-404"}, "correlation_id": "corr-404"})

    assert result == {
        "error": "mission store unavailable",
        "from": "mission-converter",
    }
