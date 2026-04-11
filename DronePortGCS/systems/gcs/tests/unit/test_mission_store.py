import json

import pytest

from systems.gcs.src.mission_store.src.mission_store import MissionStoreComponent
from systems.gcs.src.mission_store.topics import MissionStoreActions


@pytest.fixture
def component(mock_bus, patch_redis_backend):
    return MissionStoreComponent(component_id="mission-store", bus=mock_bus)


def test_registers_store_handlers(component):
    assert MissionStoreActions.SAVE_MISSION in component._handlers
    assert MissionStoreActions.GET_MISSION in component._handlers
    assert MissionStoreActions.UPDATE_MISSION in component._handlers


def test_mission_key_uses_expected_namespace(component):
    assert component._mission_key("m-1") == "gcs:mission:m-1"


def test_read_json_returns_none_for_missing_key(component):
    component.redis_client.get.return_value = None

    assert component._read_json("missing") is None


def test_handle_save_mission_persists_payload(component):
    mission = {"mission_id": "m-save", "status": "created"}

    component._handle_save_mission({"payload": {"mission": mission}, "correlation_id": "corr-save"})

    component.redis_client.set.assert_called_once_with(
        "gcs:mission:m-save",
        json.dumps(mission, ensure_ascii=False),
    )


def test_handle_get_mission_returns_component_and_mission(component):
    component._read_mission = lambda mission_id: {"mission_id": mission_id, "status": "created"}

    result = component._handle_get_mission({"payload": {"mission_id": "m-get"}, "correlation_id": "corr-get"})

    assert result == {
        "from": "mission-store",
        "mission": {"mission_id": "m-get", "status": "created"},
    }


def test_handle_update_mission_merges_fields_and_updates_timestamp(component):
    written = []
    component._read_mission = lambda mission_id: {"mission_id": mission_id, "status": "created", "name": "demo"}
    component._write_mission = lambda mission: written.append(mission)

    component._handle_update_mission(
        {
            "payload": {
                "mission_id": "m-update",
                "fields": {"status": "assigned", "assigned_drone": "dr-1"},
            },
            "correlation_id": "corr-update",
        }
    )

    assert written[0]["mission_id"] == "m-update"
    assert written[0]["status"] == "assigned"
    assert written[0]["assigned_drone"] == "dr-1"
    assert written[0]["updated_at"]
