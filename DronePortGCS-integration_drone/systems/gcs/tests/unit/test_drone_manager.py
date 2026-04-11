import pytest

from systems.gcs.topics import DroneActions, DroneTopics
from systems.gcs.src.contracts import DroneStatus, MissionStatus
from systems.gcs.src.drone_manager.src.drone_manager import DroneManagerComponent
from systems.gcs.src.drone_manager.topics import ComponentTopics
from systems.gcs.src.drone_store.topics import DroneStoreActions
from systems.gcs.src.mission_store.topics import MissionStoreActions


@pytest.fixture
def component(mock_bus):
    return DroneManagerComponent(component_id="drone-manager", bus=mock_bus)


def test_handle_mission_upload(component, mock_bus):
    mock_bus.request.return_value = {"target_response": {"success": True, "payload": {"ok": True}}}

    component._handle_mission_upload(
        {
            "payload": {
                "mission_id": "m-upload",
                "drone_id": "dr-1",
                "wpl": "QGC WPL 110",
            },
            "correlation_id": "corr-3",
        }
    )

    mock_bus.request.assert_called_once_with(
        DroneTopics.SECURITY_MONITOR,
        {
            "action": DroneActions.PROXY_REQUEST,
            "sender": ComponentTopics.GCS_DRONE,
            "payload": {
                "target": {
                    "topic": DroneTopics.MISSION_HANDLER,
                    "action": DroneActions.LOAD_MISSION,
                },
                "data": {
                    "mission_id": "m-upload",
                    "wpl_content": "QGC WPL 110",
                },
            },
            "correlation_id": "corr-3",
        },
        timeout=10.0,
    )
    assert mock_bus.publish.call_count == 2
    assert mock_bus.publish.call_args_list[0].args == (
        ComponentTopics.GCS_MISSION_STORE,
        {
            "action": MissionStoreActions.UPDATE_MISSION,
            "sender": "drone-manager",
            "payload": {
                "mission_id": "m-upload",
                "fields": {
                    "assigned_drone": "dr-1", 
                    "status": MissionStatus.ASSIGNED
                },
            },
            "correlation_id": "corr-3",
        },
    )
    assert mock_bus.publish.call_args_list[1].args == (
        ComponentTopics.GCS_DRONE_STORE,
        {
            "action": DroneStoreActions.UPDATE_DRONE,
            "sender": "drone-manager",
            "payload": {
                "drone_id": "dr-1", 
                "status": DroneStatus.RESERVED
            },
            "correlation_id": "corr-3",
        },
    )


def test_handle_mission_upload_keeps_local_status_updates_when_drone_rejects(component, mock_bus):
    mock_bus.request.return_value = {"target_response": {"success": True, "payload": {"ok": False, "error": "bad"}}}

    component._handle_mission_upload(
        {
            "payload": {
                "mission_id": "m-upload",
                "drone_id": "dr-1",
                "wpl": "QGC WPL 110",
            },
        }
    )

    assert mock_bus.publish.call_count == 2
    assert mock_bus.publish.call_args_list[0].args[0] == ComponentTopics.GCS_MISSION_STORE
    assert mock_bus.publish.call_args_list[1].args[0] == ComponentTopics.GCS_DRONE_STORE


def test_save_telemetry(component, mock_bus):
    component._save_telemetry({"drone_id": "dr-2"}, correlation_id="corr-4")

    assert mock_bus.publish.call_args.args == (
        ComponentTopics.GCS_DRONE_STORE,
        {
            "action": DroneStoreActions.SAVE_TELEMETRY,
            "sender": "drone-manager",
            "payload": {"telemetry": {"drone_id": "dr-2"}},
            "correlation_id": "corr-4",
        },
    )


def test_proxy_request_drone_unwraps_security_monitor_payload(component, mock_bus):
    nested_response = {"success": True, "payload": {"telemetry": {"battery": 61}}}
    mock_bus.request.return_value = {
        "payload": {
            "target_topic": DroneTopics.TELEMETRY,
            "target_action": DroneActions.TELEMETRY_GET,
            "target_response": nested_response,
        }
    }

    response = component._proxy_request_drone(
        DroneTopics.TELEMETRY,
        DroneActions.TELEMETRY_GET,
        {"drone_id": "dr-2"},
    )

    assert response == nested_response


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ({"payload": {"telemetry": {"drone_id": "dr-2", "battery": 90}}}, {"drone_id": "dr-2", "battery": 90}),
        (
            {
                "payload": {
                    "target_response": {
                        "payload": {
                            "navigation": {"payload": {"lat": 55.65, "lon": 37.61, "alt_m": 121.5}},
                            "motors": {"battery": 63},
                        }
                    }
                }
            },
            {"latitude": 55.65, "longitude": 37.61, "altitude": 121.5, "battery": 63},
        ),
        (
            {"payload": {"navigation": {"payload": {"lat": 55.7, "lon": 37.6, "alt_m": 120.0}}}},
            {"latitude": 55.7, "longitude": 37.6, "altitude": 120.0},
        ),
        (
            {"payload": {"navigation": {"nav_state": {"lat": 55.8, "lon": 37.7, "alt_m": 121.0}}}},
            {"latitude": 55.8, "longitude": 37.7, "altitude": 121.0},
        ),
        (
            {
                "payload": {
                    "navigation": {"payload": {"lat": 55.9, "lon": 37.8, "alt_m": 122.0}},
                    "motors": {"battery": 64},
                }
            },
            {"latitude": 55.9, "longitude": 37.8, "altitude": 122.0, "battery": 64},
        ),
        ({}, None),
    ],
)
def test_normalize_telemetry(component, response, expected):
    assert component._normalize_telemetry(response) == expected


def test_handle_mission_start(component, mock_bus, monkeypatch):
    started = []
    monkeypatch.setattr(component, "_start_telemetry_polling", lambda drone_id: started.append(drone_id))
    mock_bus.request.return_value = {"target_response": {"success": True, "payload": {"ok": True, "state": "EXECUTING"}}}

    component._handle_mission_start(
        {
            "payload": {"mission_id": "m-run", "drone_id": "dr-3"},
            "correlation_id": "corr-5",
        }
    )

    mock_bus.request.assert_called_once_with(
        DroneTopics.SECURITY_MONITOR,
        {
            "action": DroneActions.PROXY_REQUEST,
            "sender": ComponentTopics.GCS_DRONE,
            "payload": {
                "target": {
                    "topic": DroneTopics.AUTOPILOT,
                    "action": DroneActions.CMD,
                },
                "data": {
                    "command": "START",
                },
            },
            "correlation_id": "corr-5",
        },
        timeout=10.0,
    )
    assert mock_bus.publish.call_count == 2
    assert mock_bus.publish.call_args_list[0].args == (
        ComponentTopics.GCS_MISSION_STORE,
        {
            "action": MissionStoreActions.UPDATE_MISSION,
            "sender": "drone-manager",
            "payload": {
                "mission_id": "m-run",
                "fields": {
                    "status": MissionStatus.RUNNING
                }
            },
            "correlation_id": "corr-5",
        },
    )
    assert mock_bus.publish.call_args_list[1].args == (
        ComponentTopics.GCS_DRONE_STORE,
        {
            "action": DroneStoreActions.UPDATE_DRONE,
            "sender": "drone-manager",
            "payload": {
                "drone_id": "dr-3",
                "status": DroneStatus.BUSY
            },
            "correlation_id": "corr-5",
        },
    )
    assert started == ["dr-3"]


def test_poll_telemetry_loop_requests_drone_and_saves_response(component, mock_bus, monkeypatch):
    component._running = True
    component._telemetry_poll_interval_s = 0.0

    class OneShotEvent:
        def __init__(self):
            self.calls = 0

        def wait(self, timeout):
            self.calls += 1
            return self.calls > 1

    saved = []
    monkeypatch.setattr(component, "_save_telemetry", lambda telemetry, correlation_id=None: saved.append(telemetry))
    mock_bus.request.return_value = {"target_response": {"payload": {"telemetry": {"battery": 61}}}}

    component._poll_telemetry_loop("dr-9", OneShotEvent())

    mock_bus.request.assert_called_once_with(
        DroneTopics.SECURITY_MONITOR,
        {
            "action": DroneActions.PROXY_REQUEST,
            "sender": ComponentTopics.GCS_DRONE,
            "payload": {
                "target": {
                    "topic": DroneTopics.TELEMETRY,
                    "action": DroneActions.TELEMETRY_GET,
                },
                "data": {"drone_id": "dr-9"},
            },
        },
        timeout=5.0,
    )
    assert saved == [{"drone_id": "dr-9", "battery": 61}]
