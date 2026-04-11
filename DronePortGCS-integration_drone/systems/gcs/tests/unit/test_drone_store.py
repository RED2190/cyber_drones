import json

import pytest

from systems.gcs.src.drone_store.src.drone_store import DroneStoreComponent
from systems.gcs.src.drone_store.topics import DroneStoreActions


@pytest.fixture
def component(mock_bus, patch_redis_backend):
    return DroneStoreComponent(component_id="drone-store", bus=mock_bus)


def test_write_drone_tracks_available_drone(component):
    state = {
        "status": "available", 
        "battery": 90
    }

    component._write_drone("dr-1", state)
    
    component.redis_client.set.assert_called_once_with(
        "gcs:drone:dr-1",
        json.dumps(state, ensure_ascii=False),
    )
    component.redis_client.sadd.assert_any_call("gcs:drones:all", "dr-1")
    component.redis_client.sadd.assert_any_call("gcs:drones:available", "dr-1")


def test_write_drone_removes_unavailable_drone(component):
    component._write_drone("dr-2", {
        "status": "reserved"
        })

    component.redis_client.srem.assert_called_once_with("gcs:drones:available", "dr-2")


def test_update_drone_from_telemetry(component):
    writes = []
    component._read_drone = lambda drone_id: None
    component._write_drone = lambda drone_id, state: writes.append((drone_id, state))

    component._update_drone_from_telemetry(
        "dr-3",
        {
            "battery": 77,
            "latitude": 55.7,
            "longitude": 37.6,
            "altitude": 120.0,
        },
    )

    assert writes[0][0] == "dr-3"
    assert writes[0][1]["status"] == "connected"
    assert writes[0][1]["battery"] == 77
    assert writes[0][1]["last_position"] == {
        "latitude": 55.7,
        "longitude": 37.6,
        "altitude": 120.0,
    }
    assert writes[0][1]["connected_at"]


def test_handle_save_telemetry(component):
    calls = []
    component._update_drone_from_telemetry = lambda drone_id, telemetry: calls.append((drone_id, telemetry))

    component._handle_save_telemetry(
        {
            "payload": {
                "telemetry": {
                    "drone_id": "dr-4",
                    "battery": 40,
                }
            },
            "correlation_id": "corr-telemetry",
        }
    )

    assert calls == [("dr-4", {"drone_id": "dr-4", "battery": 40})]


def test_handle_get_drone_returns_saved_state(component):
    component._read_drone = lambda drone_id: {"drone_id": drone_id, "status": "busy"}

    result = component._handle_get_drone(
        {"payload": {"drone_id": "dr-4"}, "correlation_id": "corr-get-drone"}
    )

    assert result == {
        "from": "drone-store",
        "drone": {"drone_id": "dr-4", "status": "busy"},
    }


def test_handle_update_drone_overrides_status(component):
    writes = []
    component._read_drone = lambda drone_id: {"battery": 50, "status": "connected"}
    component._write_drone = lambda drone_id, state: writes.append((drone_id, state))

    component._handle_update_drone(
        {"payload": {"drone_id": "dr-5", "status": "available"}, "correlation_id": "corr-update"}
    )

    assert writes == [("dr-5", {"battery": 50, "status": "available"})]
