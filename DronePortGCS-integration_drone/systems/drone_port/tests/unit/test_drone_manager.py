from systems.drone_port.src.drone_manager.src.drone_manager import DroneManager
from systems.drone_port.src.drone_registry.topics import ComponentTopics as RegistryTopics, DroneRegistryActions
from systems.drone_port.src.port_manager.topics import PortManagerActions


def test_landing_registers_drone_after_port_assignment(mock_bus):
    manager = DroneManager(component_id="drone_manager", name="DroneManager", bus=mock_bus)
    mock_bus.request.return_value = {"port_id": "P-01"}

    result = manager._handle_landing({"payload": {"drone_id": "DR-1", "model": "QuadroX"}})

    assert result == {"port_id": "P-01", "from": "drone_manager"}
    assert mock_bus.publish.call_args.args == (
        RegistryTopics.DRONE_REGISTRY,
        {
            "action": DroneRegistryActions.REGISTER_DRONE,
            "payload": {
                "drone_id": "DR-1",
                "model": "QuadroX",
                "port_id": "P-01",
            },
            "sender": "drone_manager",
        },
    )


def test_takeoff_publishes_port_release_and_sitl_start(mock_bus, patch_drone_manager_external):
    manager = DroneManager(component_id="drone_manager", name="DroneManager", bus=mock_bus)

    def request_side_effect(topic, message, timeout=None):
        if message["action"] == PortManagerActions.GET_PORT_STATUS:
            return {
                "ports": [
                    {
                        "port_id": "P-01",
                        "drone_id": "DR-1",
                        "lat": "55.751000",
                        "lon": "37.617000",
                    }
                ]
            }
        return {"success": True, "battery": "90", "port_id": "P-01"}

    mock_bus.request.side_effect = request_side_effect

    result = manager._handle_takeoff({"payload": {"drone_id": "DR-1"}})

    assert result["battery"] == 90.0
    assert result["port_id"] == "P-01"
    assert result["port_coordinates"] == {"lat": "55.751000", "lon": "37.617000"}
    assert mock_bus.publish.call_args_list[0].args == (
        "v1.drone_port.1.port_manager",
        {
            "action": "free_slot",
            "payload": {"drone_id": "DR-1", "port_id": "P-01"},
            "sender": "drone_manager",
        },
    )
    assert mock_bus.publish.call_args_list[1].args == (
        "sitl-drone-home",
        {
            "drone_id": "DR-1",
            "home_lat": 55.751,
            "home_lon": 37.617,
            "home_alt": 10.0,
        },
    )
