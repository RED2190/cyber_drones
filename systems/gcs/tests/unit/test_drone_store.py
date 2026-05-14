import json

import pytest

from ...src.drone_store.src.drone_store import DroneStoreComponent
from ...src.drone_store.topics import DroneStoreActions


@pytest.fixture
def component(mock_bus, patch_redis_backend):
    return DroneStoreComponent(component_id="drone-store", bus=mock_bus)


# -------------------------
# Регистрация обработчиков
# -------------------------
def test_registers_drone_store_handlers(component):
    """Все действия DroneStore зарегистрированы в _handlers."""
    assert DroneStoreActions.UPDATE_DRONE in component._handlers
    assert DroneStoreActions.SAVE_TELEMETRY in component._handlers


# -------------------------
# Ключи Redis
# -------------------------
def test_drone_keys_use_expected_namespace(component):
    """Префиксы ключей совпадают с логикой хранения флота."""
    assert component._drone_key("dr-1") == "gcs:drone:dr-1"
    assert component._all_drones_key() == "gcs:drones:all"
    assert component._available_drones_key() == "gcs:drones:available"


# -------------------------
# _write_drone: set + множества all / available
# -------------------------
def test_write_drone_tracks_available_drone(component):
    """Доступный дрон попадает в множество available."""
    state = {"status": "available", "battery": 90}

    component._write_drone("dr-1", state)

    component.redis_client.set.assert_called_once_with(
        "gcs:drone:dr-1",
        json.dumps(state, ensure_ascii=False),
    )
    component.redis_client.sadd.assert_any_call("gcs:drones:all", "dr-1")
    component.redis_client.sadd.assert_any_call("gcs:drones:available", "dr-1")


def test_write_drone_removes_unavailable_drone(component):
    """Статус не available - убираем из множества available."""
    component._write_drone("dr-2", {"status": "reserved"})

    component.redis_client.srem.assert_called_once_with("gcs:drones:available", "dr-2")


# -------------------------
# _update_drone_from_telemetry
# -------------------------
def test_update_drone_from_telemetry_new_drone(component):
    """Новый дрон: connected, батарея, last_position при полных координатах."""
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


def test_update_drone_from_telemetry_without_position_does_not_set_last_position(component):
    """Без пары lat+lon last_position не создаётся."""
    writes = []
    component._read_drone = lambda drone_id: None
    component._write_drone = lambda drone_id, state: writes.append((drone_id, state))

    component._update_drone_from_telemetry(
        "dr-6",
        {"battery": 55},
    )

    assert writes[0][0] == "dr-6"
    assert "last_position" not in writes[0][1]


def test_update_drone_from_telemetry_only_latitude_no_last_position(component):
    """Только latitude без longitude - last_position не ставим (текущее правило)."""
    writes = []
    component._read_drone = lambda drone_id: None
    component._write_drone = lambda drone_id, state: writes.append((drone_id, state))

    component._update_drone_from_telemetry("dr-lat-only", {"latitude": 55.0, "battery": 10})

    assert "last_position" not in writes[0][1]


def test_update_drone_from_telemetry_without_battery_keeps_existing_battery(component):
    """Нет ключа battery в телеметрии - старое значение батареи не трогаем."""
    writes = []
    component._read_drone = lambda drone_id: {"battery": 80, "status": "connected"}
    component._write_drone = lambda drone_id, state: writes.append((drone_id, state))

    component._update_drone_from_telemetry(
        "dr-7",
        {"latitude": 55.0, "longitude": 37.0},
    )

    assert writes[0][0] == "dr-7"
    assert writes[0][1]["battery"] == 80
    assert writes[0][1]["last_position"]["latitude"] == 55.0
    assert writes[0][1]["last_position"]["longitude"] == 37.0


def test_update_drone_from_telemetry_battery_none_keeps_existing(component):
    """battery: None в телеметрии - не трогаем сохранённое значение батареи."""
    writes = []
    component._read_drone = lambda drone_id: {"battery": 50, "status": "connected"}
    component._write_drone = lambda drone_id, state: writes.append((drone_id, state))

    component._update_drone_from_telemetry("dr-batt", {"battery": None})

    assert writes[0][1]["battery"] == 50


def test_update_drone_from_telemetry_invalid_battery_value_skipped(component):
    """Нечисловой battery - не падаем, старое значение сохраняется."""
    writes = []
    component._read_drone = lambda drone_id: {"battery": 50, "status": "connected"}
    component._write_drone = lambda drone_id, state: writes.append((drone_id, state))

    component._update_drone_from_telemetry("dr-batt", {"battery": "nope"})

    assert writes[0][1]["battery"] == 50


# -------------------------
# SAVE_TELEMETRY (_handle_save_telemetry)
# -------------------------
def test_handle_save_telemetry_delegates_to_update(component):
    """Хендлер передаёт drone_id и полный словарь телеметрии в _update_drone_from_telemetry."""
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
    """Существующее состояние из Redis мержится, status перезаписывается."""
    writes = []
    component._read_drone = lambda drone_id: {"battery": 50, "status": "connected"}
    component._write_drone = lambda drone_id, state: writes.append((drone_id, state))

    component._handle_update_drone(
        {"payload": {"drone_id": "dr-5", "status": "available"}, "correlation_id": "corr-update"}
    )

    assert writes == [("dr-5", {"battery": 50, "status": "available"})]


def test_handle_update_drone_for_new_drone_creates_state(component):
    """Нет записи в Redis - создаём словарь только со status."""
    writes = []
    component._read_drone = lambda drone_id: None
    component._write_drone = lambda drone_id, state: writes.append((drone_id, state))

    component._handle_update_drone({"payload": {"drone_id": "dr-8", "status": "available"}})

    assert writes == [("dr-8", {"status": "available"})]


# -------------------------
# Ввод с ошибками
# -------------------------
def test_handle_save_telemetry_ignores_invalid_payload(component):
    """payload не dict - ничего не делаем, None на выходе."""
    calls = []
    component._update_drone_from_telemetry = lambda *a: calls.append(a)

    assert component._handle_save_telemetry({"payload": None}) is None
    assert calls == []


def test_handle_save_telemetry_ignores_missing_telemetry(component):
    """Нет telemetry или не словарь - выход без обновления."""
    calls = []
    component._update_drone_from_telemetry = lambda *a: calls.append(a)

    with pytest.raises(AttributeError):
        component._handle_save_telemetry({"payload": {}})
    assert calls == []

    with pytest.raises(AttributeError):
        component._handle_save_telemetry({"payload": {"telemetry": "bad"}})
    assert calls == []


def test_handle_save_telemetry_ignores_non_dict_message(component):
    """message не словарь - безопасный выход."""
    calls = []
    component._update_drone_from_telemetry = lambda *a: calls.append(a)

    assert component._handle_save_telemetry(None) is None  # type: ignore[arg-type]
    assert calls == []


def test_handle_save_telemetry_ignores_missing_drone_id(component):
    """При отсутствии drone_id хендлер всё равно прокидывает telemetry дальше."""
    calls = []
    component._update_drone_from_telemetry = lambda *a: calls.append(a)

    assert (
        component._handle_save_telemetry({"payload": {"telemetry": {"battery": 99}}})
        is None
    )
    assert calls == [(None, {"battery": 99})]


def test_handle_update_drone_ignores_missing_drone_id(component):
    """Без drone_id не пишем в Redis."""
    writes = []
    component._read_drone = lambda drone_id: None
    component._write_drone = lambda drone_id, state: writes.append((drone_id, state))

    component._handle_update_drone({"payload": {"status": "available"}})

    assert writes == []


def test_read_drone_invalid_json_from_redis_returns_none(component):
    """Битый JSON в Redis - как отсутствующая запись."""
    component.redis_client.get.return_value = b"not-json{"

    assert component._read_drone("dr-bad") is None


def test_write_drone_invalid_id_does_not_touch_redis(component):
    """Пустой/невалидный id - не вызываем set/sadd/srem."""
    component._write_drone("", {"status": "available"})
    component._write_drone(None, {"status": "available"})

    component.redis_client.set.assert_not_called()

# -------------------------
# _normalize_drone_id: int и некорректные типы
# -------------------------
def test_normalize_drone_id_handles_int_and_invalid_types():
    from ...src.drone_store.src.drone_store import DroneStoreComponent

    assert DroneStoreComponent._normalize_drone_id(123) == "123"
    assert DroneStoreComponent._normalize_drone_id(0) == "0"
    assert DroneStoreComponent._normalize_drone_id(3.14) is None
    assert DroneStoreComponent._normalize_drone_id([]) is None
    assert DroneStoreComponent._normalize_drone_id({}) is None

# -------------------------
# _read_drone: None и битый JSON
# -------------------------
def test_read_drone_various_cases(component):
    # Некорректный drone_id
    assert component._read_drone(None) is None
    assert component._read_drone("") is None

    # Redis вернул None
    component.redis_client.get.return_value = None
    assert component._read_drone("dr-1") is None

    # Redis вернул битый JSON
    component.redis_client.get.return_value = b"{bad-json"
    assert component._read_drone("dr-2") is None

    # Redis вернул валидный JSON
    component.redis_client.get.return_value = json.dumps({"status": "available"}).encode()
    result = component._read_drone("dr-3")
    assert result == {"status": "available"}

# -------------------------
# _all_drone_ids / _available_drone_ids возвращают пустой набор при пустом Redis
# -------------------------
def test_all_and_available_drone_ids_empty_sets(component):
    component.redis_client.smembers.return_value = set()
    assert component._all_drone_ids() == set()
    assert component._available_drone_ids() == set()
# -------------------------
# _update_drone_from_telemetry: drone_id None
# -------------------------
def test_update_drone_from_telemetry_with_none_drone_id(component):
    # Ни один write не должен быть вызван
    writes = []
    component._write_drone = lambda drone_id, state: writes.append((drone_id, state))
    component._update_drone_from_telemetry(None, {"battery": 50})
    assert writes == []

# -------------------------
# _handle_update_drone: message и payload некорректного типа
# -------------------------
def test_handle_update_drone_invalid_types(component):
    # message не dict
    assert component._handle_update_drone(None) is None  # type: ignore[arg-type]

    # payload не dict
    assert component._handle_update_drone({"payload": None}) is None

    # drone_id некорректный
    assert component._handle_update_drone({"payload": {"drone_id": None}}) is None




