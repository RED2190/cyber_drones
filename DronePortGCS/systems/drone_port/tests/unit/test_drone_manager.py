from systems.drone_port.src.drone_manager.src.drone_manager import DroneManager
from systems.drone_port.src.charging_manager.topics import ComponentTopics as ChargingTopics, ChargingManagerActions
from systems.drone_port.src.drone_manager.topics import DroneManagerActions
from systems.drone_port.src.drone_registry.topics import ComponentTopics as RegistryTopics, DroneRegistryActions
from systems.drone_port.src.port_manager.topics import PortManagerActions


def test_landing_registers_drone_after_port_assignment(mock_bus):
    manager = DroneManager(component_id="drone_manager", name="DroneManager", bus=mock_bus)
    mock_bus.request.return_value = {"success": True, "payload": {"port_id": "P-01"}}

    result = manager._handle_landing({"payload": {"drone_id": "DR-1", "model": "QuadroX"}})

    assert result == {"approved": True, "port_id": "P-01", "drone_id": "DR-1", "from": "drone_manager"}
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


def test_takeoff_publishes_port_release_and_sitl_home(mock_bus, patch_drone_manager_external):
    manager = DroneManager(component_id="drone_manager", name="DroneManager", bus=mock_bus)

    def request_side_effect(topic, message, timeout=None):
        if message["action"] == PortManagerActions.GET_PORT_STATUS:
            return {
                "success": True,
                "payload": {
                    "ports": [
                        {
                            "port_id": "P-01",
                            "drone_id": "DR-1",
                            "lat": "55.751000",
                            "lon": "37.617000",
                        }
                    ]
                },
            }
        return {
            "success": True,
            "payload": {"success": True, "battery": "90", "port_id": "P-01"},
        }

    mock_bus.request.side_effect = request_side_effect

    result = manager._handle_takeoff({"payload": {"drone_id": "DR-1"}})

    assert result["approved"] is True
    assert result["battery"] == 90.0
    assert result["port_id"] == "P-01"
    assert result["drone_id"] == "DR-1"
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
        "sitl",
        {
            "drone_id": "DR-1",
            "home_lat": 55.751,
            "home_lon": 37.617,
            "home_alt": 0.0,
        },
    )
    assert len(mock_bus.publish.call_args_list) == 2


def test_takeoff_returns_domain_error_when_battery_is_unknown(mock_bus, patch_drone_manager_external):
    manager = DroneManager(component_id="drone_manager", name="DroneManager", bus=mock_bus)

    def request_side_effect(topic, message, timeout=None):
        if message["action"] == PortManagerActions.GET_PORT_STATUS:
            return {
                "success": True,
                "payload": {
                    "ports": [
                        {
                            "port_id": "P-01",
                            "drone_id": "DR-1",
                            "lat": "55.751000",
                            "lon": "37.617000",
                        }
                    ]
                },
            }
        return {
            "success": True,
            "payload": {"success": True, "battery": "unknown", "port_id": "P-01"},
        }

    mock_bus.request.side_effect = request_side_effect

    result = manager._handle_takeoff({"payload": {"drone_id": "DR-1"}})

    assert result == {
        "error": "Battery level is unknown",
        "from": "drone_manager",
    }
    assert mock_bus.publish.call_count == 0


def test_external_landing_uses_sender_topic_as_drone_id(mock_bus):
    manager = DroneManager(component_id="drone_manager", name="DroneManager", bus=mock_bus)
    mock_bus.request.return_value = {"success": True, "payload": {"port_id": "P-02"}}

    result = manager._handle_landing(
        {
            "sender": "v1.Agrodron.Agrodron001.security_monitor",
            "payload": {},
        }
    )

    assert result == {"approved": True, "port_id": "P-02", "drone_id": "Agrodron001", "from": "drone_manager"}
    assert mock_bus.publish.call_args.args[1]["payload"]["drone_id"] == "Agrodron001"


def test_landing_with_partial_battery_starts_charging(mock_bus):
    manager = DroneManager(component_id="drone_manager", name="DroneManager", bus=mock_bus)
    mock_bus.request.return_value = {"success": True, "payload": {"port_id": "P-03"}}

    result = manager._handle_landing(
        {"payload": {"drone_id": "DR-9", "model": "QuadroX", "battery": 72.5}}
    )

    assert result == {"approved": True, "port_id": "P-03", "drone_id": "DR-9", "from": "drone_manager"}
    assert mock_bus.publish.call_args_list[0].args == (
        RegistryTopics.DRONE_REGISTRY,
        {
            "action": DroneRegistryActions.REGISTER_DRONE,
            "payload": {
                "drone_id": "DR-9",
                "model": "QuadroX",
                "port_id": "P-03",
            },
            "sender": "drone_manager",
        },
    )
    assert mock_bus.publish.call_args_list[1].args == (
        RegistryTopics.DRONE_REGISTRY,
        {
            "action": DroneRegistryActions.UPDATE_BATTERY,
            "payload": {
                "drone_id": "DR-9",
                "battery": 72.5,
            },
            "sender": "drone_manager",
        },
    )
    assert mock_bus.publish.call_args_list[2].args == (
        ChargingTopics.CHARGING_MANAGER,
        {
            "action": ChargingManagerActions.START_CHARGING,
            "payload": {
                "drone_id": "DR-9",
                "battery": 72.5,
            },
            "sender": "drone_manager",
        },
    )


def test_landing_with_full_battery_does_not_start_charging(mock_bus):
    manager = DroneManager(component_id="drone_manager", name="DroneManager", bus=mock_bus)
    mock_bus.request.return_value = {"success": True, "payload": {"port_id": "P-04"}}

    manager._handle_landing(
        {"payload": {"drone_id": "DR-10", "model": "QuadroX", "battery": 100}}
    )

    assert mock_bus.publish.call_args_list[0].args[0] == RegistryTopics.DRONE_REGISTRY
    assert mock_bus.publish.call_args_list[1].args == (
        RegistryTopics.DRONE_REGISTRY,
        {
            "action": DroneRegistryActions.UPDATE_BATTERY,
            "payload": {
                "drone_id": "DR-10",
                "battery": 100.0,
            },
            "sender": "drone_manager",
        },
    )
    assert len(mock_bus.publish.call_args_list) == 2


def test_request_takeoff_reuses_takeoff_handler(mock_bus, patch_drone_manager_external):
    manager = DroneManager(component_id="drone_manager", name="DroneManager", bus=mock_bus)

    def request_side_effect(topic, message, timeout=None):
        if message["action"] == PortManagerActions.GET_PORT_STATUS:
            return {
                "success": True,
                "payload": {
                    "ports": [
                        {
                            "port_id": "P-07",
                            "drone_id": "Agrodron001",
                            "lat": "55.751000",
                            "lon": "37.617000",
                        }
                    ]
                },
            }
        return {
            "success": True,
            "payload": {"success": True, "battery": "95", "port_id": "P-07"},
        }

    mock_bus.request.side_effect = request_side_effect

    result = manager._handlers[DroneManagerActions.REQUEST_TAKEOFF](
        {
            "sender": "v1.Agrodron.Agrodron001.security_monitor",
            "payload": {"mission_id": "mission-001"},
        }
    )

    assert result["approved"] is True
    assert result["drone_id"] == "Agrodron001"
