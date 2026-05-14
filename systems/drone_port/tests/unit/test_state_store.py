import pytest

from systems.drone_port.src.state_store.src.state_store import StateStore
from systems.drone_port.src.state_store.topics import StateStoreActions

def test_registers_state_store_handlers(mock_bus, patch_droneport_redis):
    store = StateStore(component_id="state_store", name="StateStore", bus=mock_bus)

    assert StateStoreActions.GET_ALL_PORTS in store._handlers
    assert StateStoreActions.UPDATE_PORT in store._handlers

def test_state_store_seeds_default_ports_with_coordinates(mock_bus, patch_droneport_redis):
    store = StateStore(component_id="state_store", name="StateStore", bus=mock_bus)

    result = store._handle_get_all_ports({"payload": {}})

    assert len(result["ports"]) == 4
    assert result["ports"][0]["port_id"] == "P-01"
    assert result["ports"][0]["drone_id"] == "drone_001"
    assert result["ports"][0]["status"] == "reserved"
    assert result["ports"][0]["lat"] == "55.751000"
    assert result["ports"][0]["lon"] == "37.617000"


def test_state_store_updates_port_assignment(mock_bus, patch_droneport_redis):
    store = StateStore(component_id="state_store", name="StateStore", bus=mock_bus)

    result =store._handle_update_port(
        {
            "payload": {
                "port_id": "P-02",
                "drone_id": "DR-2",
                "status": "reserved",
            }
        }
    )

    assert result is None
    ports = store._handle_get_all_ports({"payload": {}})["ports"]
    port = next(item for item in ports if item["port_id"] == "P-02")
    assert port["drone_id"] == "DR-2"
    assert port["status"] == "reserved"

def test_state_store_clears_drone_id_when_none(mock_bus, patch_droneport_redis):
    store = StateStore(component_id="state_store", name="StateStore", bus=mock_bus)

    store._handle_update_port(
        {
            "payload": {
                "port_id": "P-03",
                "drone_id": None,
                "status": "free",
            }
        }
    )

    ports = store._handle_get_all_ports({"payload": {}})["ports"]
    port = next(item for item in ports if item["port_id"] == "P-03")
    assert port["drone_id"] == ""
    assert port["status"] == "free"


def test_get_all_ports_skips_missing_port_key(mock_bus, patch_droneport_redis):
    store = StateStore(component_id="state_store", name="StateStore", bus=mock_bus)

    patch_droneport_redis.delete("port:P-04")

    result = store._handle_get_all_ports({"payload": {}})

    assert len(result["ports"]) == 3
    assert all(item["port_id"] != "P-04" for item in result["ports"])

def test_state_store_init_does_not_override_existing_port(mock_bus, patch_droneport_redis):
    patch_droneport_redis.hset(
        "port:P-01",
        mapping={
            "port_id": "P-01",
            "drone_id": "DR-EXISTING",
            "status": "reserved",
            "lat": "99.000000",
            "lon": "88.000000",
        },
    )

    store = StateStore(component_id="state_store", name="StateStore", bus=mock_bus)

    ports = store._handle_get_all_ports({"payload": {}})["ports"]
    port = next(item for item in ports if item["port_id"] == "P-01")
    assert port["drone_id"] == "DR-EXISTING"
    assert port["status"] == "reserved"
    assert port["lat"] == "99.000000"
    assert port["lon"] == "88.000000"


def test_update_port_with_payload_none_raises_attribute_error(mock_bus, patch_droneport_redis):
    store = StateStore(component_id="state_store", name="StateStore", bus=mock_bus)

    with pytest.raises(AttributeError):
        store._handle_update_port({"payload": None})


def test_update_port_with_invalid_payload_type_raises_attribute_error(mock_bus, patch_droneport_redis):
    store = StateStore(component_id="state_store", name="StateStore", bus=mock_bus)

    with pytest.raises(AttributeError):
        store._handle_update_port({"payload": []})