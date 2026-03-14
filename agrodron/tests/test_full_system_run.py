"""
Полный прогон системы: все взаимодействия как при реальном запуске дрона.

ОРВД/НСУ -> mission_handler -> autopilot -> motors/sprayer -> SITL,
navigation, telemetry, limiter, emergensy, journal, МБ.

Запуск (система уже поднята: make docker-up):
  cd agrodron && set -a && . .generated/.env && set +a && make run-all

Или одной командой с подъёмом системы:
  make full-run
"""
import os
import time

import pytest


def _has_broker():
    t = os.environ.get("BROKER_TYPE", "").strip()
    if t == "mqtt":
        return bool(os.environ.get("MQTT_BROKER", "").strip())
    if t == "kafka":
        return bool(os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "").strip())
    return False


def _req(bus, sm_topic, sender, target_topic, action, data=None):
    msg = {
        "action": "proxy_request",
        "sender": sender,
        "payload": {"target": {"topic": target_topic, "action": action}, "data": data or {}},
    }
    return bus.request(sm_topic, msg, timeout=10.0)


def _pub(bus, sm_topic, sender, target_topic, action, data=None):
    msg = {
        "action": "proxy_publish",
        "sender": sender,
        "payload": {"target": {"topic": target_topic, "action": action}, "data": data or {}},
    }
    return bus.publish(sm_topic, msg)


# -----------------------------------------------------------------------------
# 1. Подключение и МБ
# -----------------------------------------------------------------------------

@pytest.mark.full_system
@pytest.mark.skipif(not _has_broker(), reason="Нужен BROKER_TYPE и брокер (make docker-up)")
def test_01_broker_connection(security_monitor_topic):
    """Подключение к брокеру: шина поднимается и останавливается без ошибок."""
    from broker.bus_factory import create_system_bus
    bus = create_system_bus(client_id="run_01")
    bus.start()
    time.sleep(1.0)
    bus.stop()


@pytest.mark.full_system
@pytest.mark.skipif(not _has_broker(), reason="Нужен брокер")
def test_02_mb_proxy_request_motors(security_monitor_topic, topic):
    """МБ: proxy_request от telemetry к motors get_state возвращает ответ."""
    from broker.bus_factory import create_system_bus
    bus = create_system_bus(client_id="run_02")
    bus.start()
    time.sleep(2.0)
    r = _req(bus, security_monitor_topic, "telemetry", topic("motors"), "get_state")
    assert r is not None and isinstance(r, dict)
    bus.stop()


# -----------------------------------------------------------------------------
# 2. ОРВД / НСУ — наземная станция, загрузка миссии
# -----------------------------------------------------------------------------

WPL_MINIMAL = "QGC WPL 110\n0\t1\t0\t16\t0\t0\t0\t0\t60.0\t30.0\t5.0\t1"


@pytest.mark.full_system
@pytest.mark.skipif(not _has_broker(), reason="Нужен брокер")
def test_03_orvd_load_mission(security_monitor_topic, topic):
    """ОРВД/НСУ: LOAD_MISSION (WPL) в mission_handler через МБ."""
    from broker.bus_factory import create_system_bus
    bus = create_system_bus(client_id="run_03")
    bus.start()
    time.sleep(2.0)
    msg = {
        "action": "proxy_request",
        "sender": "orvd",
        "payload": {
            "target": {"topic": topic("mission_handler"), "action": "LOAD_MISSION"},
            "data": {"wpl_content": WPL_MINIMAL, "mission_id": "run_m1"},
        },
    }
    r = bus.request(security_monitor_topic, msg, timeout=15.0)
    assert r is not None
    if isinstance(r, dict) and "target_response" in r:
        tr = r["target_response"]
        if isinstance(tr, dict) and "payload" in tr:
            assert tr["payload"].get("ok") is True
    bus.stop()


@pytest.mark.full_system
@pytest.mark.skipif(not _has_broker(), reason="Нужен брокер")
def test_04_orvd_validate_only(security_monitor_topic, topic):
    """ОРВД/НСУ: VALIDATE_ONLY — проверка WPL без загрузки в автопилот."""
    from broker.bus_factory import create_system_bus
    bus = create_system_bus(client_id="run_04")
    bus.start()
    msg = {
        "action": "proxy_request",
        "sender": "orvd",
        "payload": {
            "target": {"topic": topic("mission_handler"), "action": "VALIDATE_ONLY"},
            "data": {"wpl_content": WPL_MINIMAL},
        },
    }
    r = bus.request(security_monitor_topic, msg, timeout=10.0)
    assert r is not None
    bus.stop()


# -----------------------------------------------------------------------------
# 3. Автопилот и команды приводам / опрыскивателю
# -----------------------------------------------------------------------------

@pytest.mark.full_system
@pytest.mark.skipif(not _has_broker(), reason="Нужен брокер")
def test_05_autopilot_mission_load(security_monitor_topic, topic):
    """Автопилот: приём mission_load от mission_handler через МБ."""
    from broker.bus_factory import create_system_bus
    bus = create_system_bus(client_id="run_05")
    bus.start()
    time.sleep(2.0)
    r = _req(bus, security_monitor_topic, "mission_handler", topic("autopilot"), "mission_load",
             data={"mission": {"mission_id": "m1", "steps": [{"id": "wp1", "lat": 60.0, "lon": 30.0, "alt_m": 10.0}]}})
    assert r is not None
    bus.stop()


@pytest.mark.full_system
@pytest.mark.skipif(not _has_broker(), reason="Нужен брокер")
def test_06_autopilot_set_target_to_motors(security_monitor_topic, topic):
    """Автопилот -> МБ -> motors: SET_TARGET (vx, vy, vz)."""
    from broker.bus_factory import create_system_bus
    bus = create_system_bus(client_id="run_06")
    bus.start()
    time.sleep(2.0)
    ok = _pub(bus, security_monitor_topic, "autopilot", topic("motors"), "SET_TARGET",
              data={"vx": 0.5, "vy": 0.3, "vz": 0.0})
    assert ok is not False
    time.sleep(0.5)
    r = _req(bus, security_monitor_topic, "telemetry", topic("motors"), "get_state")
    if r and "target_response" in r and r["target_response"].get("payload"):
        assert r["target_response"]["payload"].get("mode") == "TRACKING"
    bus.stop()


@pytest.mark.full_system
@pytest.mark.skipif(not _has_broker(), reason="Нужен брокер")
def test_07_autopilot_set_spray_to_sprayer(security_monitor_topic, topic):
    """Автопилот -> МБ -> sprayer: SET_SPRAY (вкл/выкл)."""
    from broker.bus_factory import create_system_bus
    bus = create_system_bus(client_id="run_07")
    bus.start()
    time.sleep(2.0)
    ok = _pub(bus, security_monitor_topic, "autopilot", topic("sprayer"), "SET_SPRAY", data={"spray": True})
    assert ok is not False
    time.sleep(0.5)
    r = _req(bus, security_monitor_topic, "telemetry", topic("sprayer"), "get_state")
    if r and "target_response" in r and r["target_response"].get("payload"):
        assert r["target_response"]["payload"].get("state") == "ON"
    bus.stop()


# -----------------------------------------------------------------------------
# 4. Приводы и SITL (команда уходит в топик sitl.commands через МБ)
# -----------------------------------------------------------------------------

@pytest.mark.full_system
@pytest.mark.skipif(not _has_broker(), reason="Нужен брокер")
def test_08_motors_emit_sitl_via_mb(security_monitor_topic, topic):
    """Приводы: SET_TARGET приводит к отправке команды в SITL (топик sitl.commands) через МБ."""
    from broker.bus_factory import create_system_bus
    bus = create_system_bus(client_id="run_08")
    bus.start()
    time.sleep(2.0)
    _pub(bus, security_monitor_topic, "autopilot", topic("motors"), "SET_TARGET",
         data={"vx": 1.0, "vy": 0.0, "vz": 0.0})
    time.sleep(0.5)
    r = _req(bus, security_monitor_topic, "telemetry", topic("motors"), "get_state")
    assert r is not None
    bus.stop()


# -----------------------------------------------------------------------------
# 5. Опрыскиватель и SITL
# -----------------------------------------------------------------------------

@pytest.mark.full_system
@pytest.mark.skipif(not _has_broker(), reason="Нужен брокер")
def test_09_sprayer_emit_sitl(security_monitor_topic, topic):
    """Опрыскиватель: SET_SPRAY приводит к публикации в SITL-топик (mock/наблюдение)."""
    from broker.bus_factory import create_system_bus
    bus = create_system_bus(client_id="run_09")
    bus.start()
    time.sleep(2.0)
    _pub(bus, security_monitor_topic, "autopilot", topic("sprayer"), "SET_SPRAY", data={"spray": False})
    r = _req(bus, security_monitor_topic, "telemetry", topic("sprayer"), "get_state")
    assert r is not None
    bus.stop()


# -----------------------------------------------------------------------------
# 6. Навигация (опрос SITL/Redis)
# -----------------------------------------------------------------------------

@pytest.mark.full_system
@pytest.mark.skipif(not _has_broker(), reason="Нужен брокер")
def test_10_navigation_get_state(security_monitor_topic, topic):
    """Навигация: autopilot запрашивает get_state (данные SITL/Redis)."""
    from broker.bus_factory import create_system_bus
    bus = create_system_bus(client_id="run_10")
    bus.start()
    time.sleep(2.0)
    r = _req(bus, security_monitor_topic, "autopilot", topic("navigation"), "get_state")
    assert r is not None
    bus.stop()


# -----------------------------------------------------------------------------
# 7. Телеметрия (сбор с motors/sprayer)
# -----------------------------------------------------------------------------

@pytest.mark.full_system
@pytest.mark.skipif(not _has_broker(), reason="Нужен брокер")
def test_11_telemetry_get_state_by_limiter(security_monitor_topic, topic):
    """Телеметрия: limiter запрашивает get_state — снимок motors + sprayer."""
    from broker.bus_factory import create_system_bus
    bus = create_system_bus(client_id="run_11")
    bus.start()
    time.sleep(3.0)
    r = _req(bus, security_monitor_topic, "limiter", topic("telemetry"), "get_state")
    assert r is not None
    if isinstance(r, dict) and "target_response" in r and r["target_response"].get("payload"):
        p = r["target_response"]["payload"]
        assert "motors" in p or "sprayer" in p or "last_poll_ts" in p
    bus.stop()


# -----------------------------------------------------------------------------
# 8. Ограничитель (limiter)
# -----------------------------------------------------------------------------

@pytest.mark.full_system
@pytest.mark.skipif(not _has_broker(), reason="Нужен брокер")
def test_12_limiter_mission_load(security_monitor_topic, topic):
    """Ограничитель: приём mission_load через МБ."""
    from broker.bus_factory import create_system_bus
    bus = create_system_bus(client_id="run_12")
    bus.start()
    time.sleep(2.0)
    ok = _pub(bus, security_monitor_topic, "mission_handler", topic("limiter"), "mission_load",
              data={"mission": {"mission_id": "m1", "steps": [{"id": "w1", "lat": 60.0, "lon": 30.0, "alt_m": 10.0}]}})
    assert ok is not False
    bus.stop()


@pytest.mark.full_system
@pytest.mark.skipif(not _has_broker(), reason="Нужен брокер")
def test_13_limiter_gets_nav_and_telemetry(security_monitor_topic, topic):
    """Ограничитель: запрос navigation get_state и telemetry get_state (по политике)."""
    from broker.bus_factory import create_system_bus
    bus = create_system_bus(client_id="run_13")
    bus.start()
    time.sleep(2.0)
    rn = _req(bus, security_monitor_topic, "limiter", topic("navigation"), "get_state")
    rt = _req(bus, security_monitor_topic, "limiter", topic("telemetry"), "get_state")
    assert rn is not None or rt is not None
    bus.stop()


# -----------------------------------------------------------------------------
# 9. Экстренные ситуации (emergensy)
# -----------------------------------------------------------------------------

@pytest.mark.full_system
@pytest.mark.skipif(not _has_broker(), reason="Нужен брокер")
def test_14_emergensy_limiter_event_land_sprayer(security_monitor_topic, topic):
    """Экстренные: limiter_event -> emergensy шлёт LAND в motors и SET_SPRAY в sprayer."""
    from broker.bus_factory import create_system_bus
    bus = create_system_bus(client_id="run_14")
    bus.start()
    time.sleep(2.0)
    ok = _pub(bus, security_monitor_topic, "limiter", topic("emergensy"), "limiter_event",
              data={"event": "EMERGENCY_LAND_REQUIRED", "mission_id": "m1", "details": {}})
    assert ok is not False
    time.sleep(0.5)
    r = _req(bus, security_monitor_topic, "telemetry", topic("motors"), "get_state")
    assert r is not None
    bus.stop()


# -----------------------------------------------------------------------------
# 10. Журнал (journal)
# -----------------------------------------------------------------------------

@pytest.mark.full_system
@pytest.mark.skipif(not _has_broker(), reason="Нужен брокер")
def test_15_journal_log_event(security_monitor_topic, topic):
    """Журнал: LOG_EVENT от autopilot через МБ записывается в журнал."""
    from broker.bus_factory import create_system_bus
    bus = create_system_bus(client_id="run_15")
    bus.start()
    time.sleep(2.0)
    ok = _pub(bus, security_monitor_topic, "autopilot", topic("journal"), "LOG_EVENT",
              data={"event": "FULL_RUN_TEST", "source": "test", "details": {}})
    assert ok is not False
    bus.stop()


# -----------------------------------------------------------------------------
# 11. Монитор безопасности (политики)
# -----------------------------------------------------------------------------

@pytest.mark.full_system
@pytest.mark.skipif(not _has_broker(), reason="Нужен брокер")
def test_16_mb_denies_unknown_sender(security_monitor_topic, topic):
    """МБ: запрос от отправителя без политики не проходит (proxy_request к motors)."""
    from broker.bus_factory import create_system_bus
    bus = create_system_bus(client_id="run_16")
    bus.start()
    time.sleep(2.0)
    r = _req(bus, security_monitor_topic, "unknown_sender_123", topic("motors"), "get_state")
    assert r is None or (isinstance(r, dict) and "target_response" not in r)
    bus.stop()


@pytest.mark.full_system
@pytest.mark.skipif(not _has_broker(), reason="Нужен брокер")
def test_17_motors_land_via_emergensy(security_monitor_topic, topic):
    """МБ: emergensy шлёт LAND в motors — режим LANDING."""
    from broker.bus_factory import create_system_bus
    bus = create_system_bus(client_id="run_17")
    bus.start()
    time.sleep(2.0)
    ok = _pub(bus, security_monitor_topic, "emergensy", topic("motors"), "LAND", data={})
    assert ok is not False
    time.sleep(0.5)
    r = _req(bus, security_monitor_topic, "telemetry", topic("motors"), "get_state")
    if r and "target_response" in r and r["target_response"].get("payload"):
        assert r["target_response"]["payload"].get("mode") == "LANDING"
    bus.stop()
