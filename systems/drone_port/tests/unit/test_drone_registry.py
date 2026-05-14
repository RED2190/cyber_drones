import pytest
from systems.drone_port.src.drone_registry.src.drone_registry import DroneRegistry
from systems.drone_port.src.drone_registry.topics import DroneRegistryActions


def test_registry_seeds_default_demo_drone(mock_bus, patch_droneport_redis):
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)

    saved = registry.redis.hgetall("drone:drone_001")
    assert saved["drone_id"] == "drone_001"
    assert saved["model"] == "AgroDron"
    assert saved["port_id"] == "P-01"
    assert saved["battery"] == "100"
    assert saved["status"] == "ready"


def test_registry_seed_does_not_override_existing_demo_drone(mock_bus, patch_droneport_redis):
    patch_droneport_redis.hset(
        "drone:drone_001",
        {
            "drone_id": "drone_001",
            "model": "CustomModel",
            "port_id": "P-99",
            "battery": "77",
            "status": "charging",
        },
    )

    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)

    saved = registry.redis.hgetall("drone:drone_001")
    assert saved["model"] == "CustomModel"
    assert saved["port_id"] == "P-99"
    assert saved["battery"] == "77"
    assert saved["status"] == "charging"


def test_register_drone_stores_metadata(mock_bus, patch_droneport_redis):
    """Новый дрон: ключ drone:{id}, статус new, модель из payload."""
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)

    registry._handle_register_drone(
        {"payload": {"drone_id": "DR-1", "model": "QuadroX", "port_id": "P-01"}}
    )

    saved = registry.redis.hgetall("drone:DR-1")
    assert saved["drone_id"] == "DR-1"
    assert saved["model"] == "QuadroX"
    assert saved["port_id"] == "P-01"
    assert saved["status"] == "new"
    assert saved["battery"] == "unknown"
    assert "registered_at" in saved
    assert "updated_at" in saved


def test_register_drone_default_model(mock_bus, patch_droneport_redis):
    """Без model подставляется unknown."""
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)

    registry._handle_register_drone({"payload": {"drone_id": "DR-2"}})

    assert registry.redis.hgetall("drone:DR-2")["model"] == "unknown"


def test_register_drone_ignores_invalid_payload(mock_bus, patch_droneport_redis):
    """Нет словаря payload или пустой drone_id - не пишем в Redis."""
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)

    registry._handle_register_drone({"payload": None})
    registry._handle_register_drone({"payload": {}})
    registry._handle_register_drone({"payload": {"model": "X"}})

    assert list(registry.redis.data) == ["drone:drone_001"]


# -------------------------
# GET_AVAILABLE_DRONES
# -------------------------
def test_get_available_drones_returns_ready_only(mock_bus, patch_droneport_redis):
    """Только дроны со статусом ready попадают в список."""
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)
    registry.redis.hset("drone:DR-1", {"drone_id": "DR-1", "status": "ready"})
    registry.redis.hset("drone:DR-2", {"drone_id": "DR-2", "status": "charging"})

    result = registry._handle_get_available_drones({"payload": {}})

    ready_by_id = {drone["drone_id"]: drone for drone in result["drones"]}
    assert ready_by_id["drone_001"]["status"] == "ready"
    assert ready_by_id["DR-1"]["status"] == "ready"
    assert result["from"] == "registry"


def test_get_available_drones_empty_when_none_ready(mock_bus, patch_droneport_redis):
    """Если новых ready-дронов нет, остаётся seeded demo-дрон."""
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)
    registry.redis.hset("drone:DR-1", {"drone_id": "DR-1", "status": "charging"})

    result = registry._handle_get_available_drones({"payload": {}})

    assert result["drones"] == [registry.redis.hgetall("drone:drone_001")]


# -------------------------
# GET_DRONE
# -------------------------
def test_get_drone_found_returns_success_and_fields(mock_bus, patch_droneport_redis):
    """Найденный дрон: success=True и поля из hash."""
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)
    registry.redis.hset(
        "drone:DR-5",
        {
            "drone_id": "DR-5",
            "status": "ready",
            "battery": "90",
            "port_id": "P-01",
        },
    )

    result = registry._handle_get_drone({"payload": {"drone_id": "DR-5"}})

    assert result["success"] is True
    assert result["from"] == "registry"
    assert result["drone_id"] == "DR-5"
    assert result["port_id"] == "P-01"
    assert result["battery"] == "90"


def test_get_drone_not_found_returns_error(mock_bus, patch_droneport_redis):
    """Нет ключа - ошибка Drone not found."""
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)

    result = registry._handle_get_drone({"payload": {"drone_id": "missing"}})

    assert result == {"error": "Drone not found", "from": "registry"}


def test_get_drone_missing_id_returns_error(mock_bus, patch_droneport_redis):
    """Без drone_id не читаем Redis."""
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)

    assert registry._handle_get_drone({"payload": {}}) == {
        "error": "drone_id required",
        "from": "registry",
    }


def test_get_drone_invalid_payload_returns_error(mock_bus, patch_droneport_redis):
    """payload не dict - понятная ошибка."""
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)

    assert registry._handle_get_drone({"payload": None}) == {
        "error": "Invalid payload",
        "from": "registry",
    }


# -------------------------
# DELETE_DRONE
# -------------------------
def test_delete_drone_removes_key(mock_bus, patch_droneport_redis):
    """DELETE удаляет hash дрона."""
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)
    registry.redis.hset("drone:DR-9", {"drone_id": "DR-9"})

    registry._handle_delete_drone({"payload": {"drone_id": "DR-9"}})

    assert "drone:DR-9" not in registry.redis.data


def test_delete_drone_invalid_id_no_op(mock_bus, patch_droneport_redis):
    """Пустой drone_id - не вызываем delete с drone:."""
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)
    registry.redis.hset("drone:DR-9", {"drone_id": "DR-9"})

    registry._handle_delete_drone({"payload": {}})

    assert "drone:DR-9" in registry.redis.data

def test_delete_drone_none_payload_no_op(mock_bus, patch_droneport_redis):
    """payload=None - не удаляем ничего"""
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)
    registry.redis.hset("drone:DR-20", {"drone_id": "DR-20"})
    registry._handle_delete_drone({"payload": None})
    assert "drone:DR-20" in registry.redis.data

# -------------------------
# CHARGING_STARTED
# -------------------------
def test_charging_started_sets_status(mock_bus, patch_droneport_redis):
    """Статус charging записывается в hash."""
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)
    registry.redis.hset("drone:DR-7", {"drone_id": "DR-7", "status": "ready"})

    registry._handle_charging_started({"payload": {"drone_id": "DR-7"}})

    assert registry.redis.hgetall("drone:DR-7")["status"] == "charging"


def test_charging_started_invalid_payload_no_write(mock_bus, patch_droneport_redis):
    """Нет валидного payload - не трогаем Redis."""
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)
    registry.redis.hset("drone:DR-7", {"drone_id": "DR-7", "status": "ready"})

    registry._handle_charging_started({"payload": None})

    assert registry.redis.hgetall("drone:DR-7")["status"] == "ready"

def test_charging_started_none_drone_id_skipped(mock_bus, patch_droneport_redis):
    """payload с пустым drone_id - не пишем статус"""
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)
    registry.redis.hset("drone:DR-21", {"drone_id": "DR-21", "status": "ready"})
    registry._handle_charging_started({"payload": {"drone_id": ""}})
    assert registry.redis.hgetall("drone:DR-21")["status"] == "ready"

# -------------------------
# UPDATE_BATTERY
# -------------------------
def test_update_battery_marks_drone_ready_at_full_charge(mock_bus, patch_droneport_redis):
    """battery 100 - статус ready и числовое значение в поле battery."""
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)
    registry.redis.hset("drone:DR-3", {"drone_id": "DR-3", "status": "charging"})

    registry._handle_update_battery({"payload": {"drone_id": "DR-3", "battery": 100}})

    saved = registry.redis.hgetall("drone:DR-3")
    assert saved["battery"] == 100.0
    assert saved["status"] == "ready"
    assert "updated_at" in saved


def test_update_battery_partial_stays_charging(mock_bus, patch_droneport_redis):
    """Заряд ниже 100 - статус charging."""
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)
    registry.redis.hset("drone:DR-4", {"drone_id": "DR-4", "status": "charging"})

    registry._handle_update_battery({"payload": {"drone_id": "DR-4", "battery": 42}})

    saved = registry.redis.hgetall("drone:DR-4")
    assert saved["battery"] == 42.0
    assert saved["status"] == "charging"


def test_update_battery_string_full_parses_to_ready(mock_bus, patch_droneport_redis):
    """Строка \"100\" приводится к float и даёт ready (как число 100)."""
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)
    registry.redis.hset("drone:DR-8", {"drone_id": "DR-8", "status": "charging"})

    registry._handle_update_battery({"payload": {"drone_id": "DR-8", "battery": "100"}})

    assert registry.redis.hgetall("drone:DR-8")["status"] == "ready"


def test_update_battery_invalid_value_skipped(mock_bus, patch_droneport_redis):
    """Нечисловой battery - не перезаписываем запись."""
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)
    registry.redis.hset("drone:DR-6", {"drone_id": "DR-6", "status": "charging", "battery": "50"})

    registry._handle_update_battery({"payload": {"drone_id": "DR-6", "battery": "oops"}})

    saved = registry.redis.hgetall("drone:DR-6")
    assert saved["battery"] == "50"
    assert saved["status"] == "charging"


def test_update_battery_missing_drone_id_skipped(mock_bus, patch_droneport_redis):
    """Нет drone_id - не пишем."""
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)

    registry._handle_update_battery({"payload": {"battery": 100}})

    assert list(registry.redis.data) == ["drone:drone_001"]

def test_update_battery_invalid_payload_skipped(mock_bus, patch_droneport_redis):
    """payload не dict — метод возвращает None и ничего не пишет в Redis."""
    registry = DroneRegistry(component_id="registry", name="Registry", bus=mock_bus)

    registry._handle_update_battery({"payload": None})

    registry._handle_update_battery({"payload": "oops"})

    registry._handle_update_battery({"payload": 42})

    assert list(registry.redis.data) == ["drone:drone_001"]
