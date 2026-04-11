from systems.drone_port.src.drone_registry.src.drone_registry import DroneRegistry


def test_registry_seeds_default_demo_drone(mock_bus, patch_droneport_redis):
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)

    saved = registry.redis.hgetall("drone:drone_001")
    assert saved["drone_id"] == "drone_001"
    assert saved["model"] == "AgroDron"
    assert saved["port_id"] == "P-01"
    assert saved["battery"] == "100"
    assert saved["status"] == "ready"


def test_register_drone_stores_metadata(mock_bus, patch_droneport_redis):
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)

    registry._handle_register_drone(
        {"payload": {"drone_id": "DR-1", "model": "QuadroX", "port_id": "P-01"}}
    )

    saved = registry.redis.hgetall("drone:DR-1")
    assert saved["drone_id"] == "DR-1"
    assert saved["model"] == "QuadroX"
    assert saved["port_id"] == "P-01"
    assert saved["status"] == "new"


def test_get_available_drones_returns_ready_only(mock_bus, patch_droneport_redis):
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)
    registry.redis.hset("drone:DR-1", {"drone_id": "DR-1", "status": "ready"})
    registry.redis.hset("drone:DR-2", {"drone_id": "DR-2", "status": "charging"})

    result = registry._handle_get_available_drones({"payload": {}})

    ready_by_id = {drone["drone_id"]: drone for drone in result["drones"]}
    assert ready_by_id["drone_001"]["status"] == "ready"
    assert ready_by_id["DR-1"]["status"] == "ready"
    assert result["from"] == "registry"


def test_update_battery_marks_drone_ready_at_full_charge(mock_bus, patch_droneport_redis):
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)
    registry.redis.hset("drone:DR-3", {"drone_id": "DR-3", "status": "charging"})

    registry._handle_update_battery({"payload": {"drone_id": "DR-3", "battery": 100}})

    saved = registry.redis.hgetall("drone:DR-3")
    assert saved["battery"] == 100
    assert saved["status"] == "ready"
