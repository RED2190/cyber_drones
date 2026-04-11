from systems.drone_port.src.state_store.src.state_store import StateStore


def test_state_store_seeds_default_ports_with_coordinates(mock_bus, patch_droneport_redis):
    store = StateStore(component_id="state_store", name="StateStore", bus=mock_bus)

    result = store._handle_get_all_ports({"payload": {}})

    assert len(result["ports"]) == 4
    assert result["ports"][0]["port_id"] == "P-01"
    assert result["ports"][0]["lat"] == "55.751000"
    assert result["ports"][0]["lon"] == "37.617000"


def test_state_store_updates_port_assignment(mock_bus, patch_droneport_redis):
    store = StateStore(component_id="state_store", name="StateStore", bus=mock_bus)

    store._handle_update_port(
        {
            "payload": {
                "port_id": "P-02",
                "drone_id": "DR-2",
                "status": "reserved",
            }
        }
    )

    ports = store._handle_get_all_ports({"payload": {}})["ports"]
    port = next(item for item in ports if item["port_id"] == "P-02")
    assert port["drone_id"] == "DR-2"
    assert port["status"] == "reserved"
