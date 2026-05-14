import json
import pytest
from datetime import datetime, timezone

from ...src.mission_store.src.mission_store import MissionStoreComponent
from ...src.mission_store.topics import MissionStoreActions


@pytest.fixture
def component(mock_bus, patch_redis_backend):
    return MissionStoreComponent(component_id="mission-store", bus=mock_bus)


# -------------------------
# Тестируем регистрацию обработчиков
# -------------------------
def test_registers_store_handlers(component):
    """Проверяет, что все ключевые действия зарегистрированы."""
    assert MissionStoreActions.SAVE_MISSION in component._handlers
    assert MissionStoreActions.GET_MISSION in component._handlers
    assert MissionStoreActions.UPDATE_MISSION in component._handlers


# -------------------------
# Тестируем формирование ключей
# -------------------------
def test_mission_key_uses_expected_namespace(component):
    """Проверяет, что ключи для Redis формируются корректно."""
    assert component._mission_key("m-1") == "gcs:mission:m-1"


# -------------------------
# Тестируем чтение JSON
# -------------------------
def test_read_json_returns_none_for_missing_key(component):
    """Если ключ отсутствует в Redis, возвращается None."""
    component.redis_client.get.return_value = None
    assert component._read_json("missing") is None


# -------------------------
# Тестируем сохранение миссии
# -------------------------
def test_handle_save_mission_persists_payload(component):
    """Проверяет, что миссия сохраняется через _write_json."""
    mission = {"mission_id": "m-save", "status": "created"}
    component._handle_save_mission({"payload": {"mission": mission}})

    component.redis_client.set.assert_called_once_with(
        "gcs:mission:m-save",
        json.dumps(mission, ensure_ascii=False),
    )


# -------------------------
# Тестируем получение миссии
# -------------------------
def test_handle_get_mission_returns_component_and_mission(component):
    """Проверяет, что возвращается словарь с mission и from."""
    component._read_mission = lambda mission_id: {"mission_id": mission_id, "status": "created"}

    result = component._handle_get_mission({"payload": {"mission_id": "m-get"}})
    assert result == {
        "from": "mission-store",
        "mission": {"mission_id": "m-get", "status": "created"},
    }


# -------------------------
# Тестируем обновление миссии
# -------------------------
def test_handle_update_mission_merges_fields_and_updates_timestamp(component):
    """Проверяет, что поля обновляются и добавляется timestamp."""
    written = []

    # Мокаем чтение и запись
    component._read_mission = lambda mission_id: {
        "mission_id": mission_id, "status": "created", "name": "demo"
    }
    component._write_mission = lambda mission: written.append(mission)

    component._handle_update_mission({
        "payload": {
            "mission_id": "m-update",
            "fields": {"status": "assigned", "assigned_drone": "dr-1"},
        }
    })

    # Проверка обновлений
    saved = written[0]
    assert saved["mission_id"] == "m-update"
    assert saved["status"] == "assigned"
    assert saved["assigned_drone"] == "dr-1"
    assert "updated_at" in saved
    # Проверка формата даты ISO
    datetime.fromisoformat(saved["updated_at"].replace("Z", "+00:00"))


def test_handle_update_mission_with_missing_fields(component):
    """Если fields отсутствуют, ничего не падает, timestamp добавляется."""
    written = []
    component._read_mission = lambda mission_id: {"mission_id": mission_id, "status": "created"}
    component._write_mission = lambda mission: written.append(mission)

    component._handle_update_mission({
        "payload": {
            "mission_id": "m-update",
            # fields отсутствуют
        }
    })

    saved = written[0]
    assert saved["mission_id"] == "m-update"
    assert saved["status"] == "created"
    assert "updated_at" in saved


def test_handle_update_mission_with_missing_mission_id(component):
    """Если mission_id отсутствует, метод безопасно ничего не делает."""
    component._read_mission = lambda mission_id: None
    component._write_mission = lambda mission: pytest.fail("Should not write mission")

    component._handle_update_mission({"payload": {"fields": {"status": "assigned"}}})


# -------------------------
# Проверяем сохранение и чтение миссии через методы _write_mission и _read_mission
# -------------------------
def test_write_and_read_json(component):
    """Проверка работы _write_json и _read_json через Redis mock."""
    key = "test-mission"
    data = {"mission_id": "m1", "status": "ok"}

    component._write_json(key, data)
    component.redis_client.set.assert_called_once_with(
        key, json.dumps(data, ensure_ascii=False)
    )

    component.redis_client.get.return_value = json.dumps(data, ensure_ascii=False)

    read_data = component._read_json(key)
    assert read_data == data

    component._read_mission = lambda mission_id: component._read_json(f"gcs:mission:{mission_id}")
    assert component._read_mission("test-mission") == data


def test_read_mission_returns_none_for_missing_key(component):
    """Если миссия отсутствует в Redis, _read_mission возвращает None."""
    # Мокаем _read_json, чтобы вернуть None
    component._read_json = lambda key: None
    assert component._read_mission("missing-mission") is None


def test_handle_update_mission_does_nothing_if_mission_not_found(component):
    """Если миссия не найдена (_read_mission возвращает None), ничего не пишем."""
    component._read_mission = lambda mission_id: None
    component._write_mission = lambda mission: pytest.fail("Should not write mission")

    component._handle_update_mission({
        "payload": {
            "mission_id": "nonexistent",
            "fields": {"status": "assigned"},
        }
    })
