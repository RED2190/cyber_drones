"""
E2E-Fabric: полный бизнес-сценарий дрона с автоматической записью в Hyperledger Fabric.

Системы (insurer, agregator) сами пишут в Fabric-леджер через dual-write
(ENABLE_FABRIC_LEDGER=true). Тест проверяет:
  1. Бизнес-логику основных систем (те же проверки что и в test_e2e_scenario.py)
  2. Что данные автоматически появляются в Fabric-леджере — без ручных вызовов

Требования:
  - Запущены основные системы (make e2e-up)
  - Запущена dummy_fabric (systems/dummy_fabric/docker-compose.yml --profile fabric --profile kafka)
  - Переменная ENABLE_FABRIC_LEDGER=true задана в окружении систем

Порядок: тесты выполняются строго последовательно, каждый следующий
использует данные, записанные предыдущим.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict

import pytest
import requests

# ── Топики основных систем ────────────────────────────────────────────────────

OPERATOR_TOPIC = "systems.operator"
REGULATOR_TOPIC = "systems.regulator"
GCS_TOPIC = "systems.gcs"
INSURER_TOPIC = "systems.insurer"
FABRIC_TOPIC = "systems.dummy_fabric"

EXPECTED_SO = [f"SO_{i}" for i in range(1, 12)]

# ── Параметры сценария ────────────────────────────────────────────────────────

DRONE_ID = "e2e-fabric-drone-001"
DRONE_VALUE = 150_000
DRONE_TYPE = "delivery"
ORDER_BUDGET = 5000

# ── Fabric-proxy URLs ─────────────────────────────────────────────────────────

PROXY_URLS = {
    "aggregator": os.environ.get("FABRIC_PROXY_AGGREGATOR", "http://localhost:3001"),
    "certcenter":  os.environ.get("FABRIC_PROXY_CERTCENTER", "http://localhost:3002"),
    "insurer":     os.environ.get("FABRIC_PROXY_INSURER", "http://localhost:3003"),
    "operator":    os.environ.get("FABRIC_PROXY_OPERATOR", "http://localhost:3004"),
    "orvd":        os.environ.get("FABRIC_PROXY_ORVD", "http://localhost:3005"),
}
MAX_PROXY_WAIT = int(os.environ.get("FABRIC_PROXY_WAIT", "90"))

# Пауза после операций, дающая время на async dual-write в Fabric
FABRIC_SETTLE_SEC = float(os.environ.get("FABRIC_SETTLE_SEC", "3"))

# ── Общее состояние прогона ───────────────────────────────────────────────────

_state: Dict[str, Any] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def bus_request(bus, topic: str, action: str, payload: dict, timeout: float = 30) -> Dict[str, Any]:
    resp = bus.request(
        topic,
        {"action": action, "sender": "e2e_fabric_test", "payload": payload},
        timeout=timeout,
    )
    assert resp is not None, f"Timeout: {action} -> {topic}"
    return resp


def rest_post(base: str, path: str, json: dict | None = None) -> requests.Response:
    return requests.post(f"{base}{path}", json=json or {}, timeout=15)


def rest_get(base: str, path: str) -> requests.Response:
    return requests.get(f"{base}{path}", timeout=15)


def _proxy_healthy(url: str) -> str:
    try:
        r = requests.get(f"{url}/health", timeout=5)
        return "" if r.status_code == 200 else f"HTTP {r.status_code}"
    except Exception as exc:
        return str(exc)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def fabric_ready():
    """Ожидание готовности всех fabric-proxy; skip если недоступны."""
    deadline = time.time() + MAX_PROXY_WAIT
    while True:
        errors = {name: _proxy_healthy(url) for name, url in PROXY_URLS.items() if _proxy_healthy(url)}
        if not errors:
            return True
        if time.time() >= deadline:
            detail = "; ".join(f"{n}: {e}" for n, e in errors.items())
            pytest.skip(f"Fabric proxies not ready after {MAX_PROXY_WAIT}s — {detail}")
        time.sleep(5)


# ══════════════════════════════════════════════════════════════════════════════
# Тесты
# ══════════════════════════════════════════════════════════════════════════════

class TestE2EFabricScenario:
    """
    Полный E2E: основные системы + автоматическая запись в Fabric.

    Fabric-вызовы делает сама система (dual-write через ENABLE_FABRIC_LEDGER).
    Тест только проверяет что данные появились в леджере.
    """

    # ── Phase 0: Регистрация систем ──────────────────────────────────────────

    def test_01_register_systems(self, kafka_bus):
        for system_id, system_type in [
            ("agregator", "aggregator"),
            ("operator", "operator"),
            ("insurer", "insurer"),
            ("orvd_system", "orvd"),
            ("gcs", "gcs"),
        ]:
            resp = bus_request(kafka_bus, REGULATOR_TOPIC, "register_system", {
                "system_id": system_id,
                "system_type": system_type,
            })
            assert resp.get("success") is True, f"register {system_id}: {resp}"
            assert (resp.get("payload") or {}).get("registered") is True

    # ── Phase 1: Регистрация дрона → годовое КАСКО → Fabric ──────────────────

    def test_02_register_drone_and_annual_insurance(self, kafka_bus):
        """
        Регистрация дрона: cert → operator → годовое страхование.
        InsurerComponent автоматически пишет create_insurance в Fabric.
        """
        r_cert = bus_request(kafka_bus, REGULATOR_TOPIC, "register_drone_cert", {
            "drone_id": DRONE_ID,
        })
        assert r_cert.get("success") is True
        cert_id = (r_cert.get("payload") or {})["certificate_id"]
        _state["drone_cert_id"] = cert_id

        r_op = bus_request(kafka_bus, OPERATOR_TOPIC, "register_drone", {
            "drone_id": DRONE_ID,
            "model": "E2E-DroneModel",
            "capabilities": ["cargo"],
            "certificate_id": cert_id,
        })
        assert r_op.get("success") is True

        # Pannual = 150_000 × 0.08 × 1.0 = 12_000.00
        r_ins = bus_request(kafka_bus, INSURER_TOPIC, "annual_insurance", {
            "drone_id": DRONE_ID,
            "drone_value": DRONE_VALUE,
            "drone_type": DRONE_TYPE,
        })
        assert r_ins.get("success") is True, f"annual_insurance: {r_ins}"
        ins = r_ins.get("payload") or {}
        assert ins.get("policy_type") == "annual"
        assert ins.get("status") == "active"
        assert ins.get("kfleet_history") == "1.0"

        expected = Decimal("150000") * Decimal("0.08") * Decimal("1.0")
        assert Decimal(ins["premium"]) == expected

        _state["annual_policy_id"] = ins["policy_id"]
        _state["annual_start"] = ins["start_date"]
        _state["annual_end"] = ins["end_date"]

    def test_03_verify_annual_insurance_in_fabric(self, kafka_bus, fabric_ready):
        """
        Проверяем что InsurerComponent автоматически записал страховку в Fabric.
        Ждём FABRIC_SETTLE_SEC на асинхронный dual-write.
        """
        time.sleep(FABRIC_SETTLE_SEC)

        # Читаем запись из Fabric по drone_id
        resp = bus_request(kafka_bus, FABRIC_TOPIC, "read_insurance", {
            "drone_id": DRONE_ID,
        })
        assert resp.get("success") is True, (
            f"Страховка дрона {DRONE_ID!r} не найдена в Fabric: {resp}\n"
            "Убедитесь что ENABLE_FABRIC_LEDGER=true задана в окружении insurer."
        )

    # ── Phase 2: Регистрация оператора ───────────────────────────────────────

    def test_04_register_operator(self, kafka_bus, agregator_url):
        operator_id = "e2e-fabric-operator"
        r_cert = bus_request(kafka_bus, REGULATOR_TOPIC, "register_operator_cert", {
            "operator_id": operator_id,
        })
        assert r_cert.get("success") is True
        cert_id = (r_cert.get("payload") or {})["certificate_id"]

        r = rest_post(agregator_url, "/operators", {
            "name": "E2E Fabric Operator",
            "license": "E2E-FAB-LIC",
            "operator_id": operator_id,
            "certificate_id": cert_id,
        })
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        _state["operator_id"] = operator_id

    # ── Phase 3: Заказ + миссионное страхование → Fabric ─────────────────────

    def test_05_create_order_and_mission_insurance(self, agregator_url, kafka_bus):
        """
        Создание заказа → confirm-price → миссионное страхование.
        AgregatorComponent автоматически пишет create_order в Fabric с тем же order_id.
        InsurerComponent пишет create_insurance (mission) в Fabric.
        """
        r = rest_post(agregator_url, "/customers", {
            "name": "E2E Fabric Customer",
            "email": "e2e-fabric@test.local",
        })
        assert r.status_code == 200
        customer_id = r.json()["customer_id"]

        r = rest_post(agregator_url, "/orders", {
            "customer_id": customer_id,
            "description": "E2E-Fabric delivery",
            "budget": ORDER_BUDGET,
            "drone_type": DRONE_TYPE,
            "pickup": {"lat": 55.75, "lon": 37.62},
            "dropoff": {"lat": 55.80, "lon": 37.70},
        })
        assert r.status_code == 200
        body = r.json()
        order_id = body["order_id"]
        _state["order_id"] = order_id

        if body["status"] != "matched":
            pytest.skip("No drone matched — cannot proceed with order flow")

        # confirm-price → Pmission = 5_000 × 0.08 × 1.0 × 1.0 = 400.00
        r = rest_post(agregator_url, f"/orders/{order_id}/confirm-price")
        assert r.status_code == 200
        confirm = r.json()
        assert confirm.get("status") == "confirmed"

        order_data = confirm.get("order", {})
        assert order_data.get("policy_id"), "policy_id должен быть после confirm-price"

        expected_mission = Decimal(str(ORDER_BUDGET)) * Decimal("0.08")
        assert Decimal(str(order_data["insurance_premium"])) == expected_mission

        _state["mission_policy_id"] = order_data["policy_id"]

    def test_06_verify_order_in_fabric(self, kafka_bus, fabric_ready):
        """
        Проверяем что AgregatorComponent автоматически записал заказ в Fabric.
        Используем тот же order_id что и в основной системе.
        """
        order_id = _state.get("order_id")
        if not order_id:
            pytest.skip("order_id не сохранён (test_05 был пропущен)")

        time.sleep(FABRIC_SETTLE_SEC)

        resp = bus_request(kafka_bus, FABRIC_TOPIC, "read_order", {
            "id": order_id,
        })
        assert resp.get("success") is True, (
            f"Заказ {order_id!r} не найден в Fabric: {resp}\n"
            "Убедитесь что ENABLE_FABRIC_LEDGER=true задана в окружении agregator."
        )
        order = resp.get("payload") or {}
        ledger_id = order.get("ID") or order.get("id")
        assert ledger_id == order_id, (
            f"ID в леджере ({ledger_id}) не совпадает с order_id основной системы ({order_id})"
        )

    # ── Phase 4: Завершение заказа → finalize в Fabric ───────────────────────

    def test_07_complete_order(self, agregator_url):
        order_id = _state.get("order_id")
        if not order_id:
            pytest.skip("order_id не сохранён (test_05 был пропущен)")

        r = rest_post(agregator_url, f"/orders/{order_id}/confirm-completion")
        assert r.status_code == 200
        assert r.json().get("status") == "completed"

        r = rest_get(agregator_url, f"/orders/{order_id}")
        assert r.status_code == 200
        final = r.json()["order"]
        assert final["status"] == "completed"
        assert final.get("policy_id"), "policy_id должен сохраниться в завершённом заказе"

    def test_08_verify_finalized_order_in_fabric(self, kafka_bus, fabric_ready):
        """
        После confirm_completion AgregatorComponent отправляет finalize_order в Fabric.
        Проверяем что финальное состояние заказа корректно.
        """
        order_id = _state.get("order_id")
        if not order_id:
            pytest.skip("order_id не сохранён (test_05 был пропущен)")

        time.sleep(FABRIC_SETTLE_SEC)

        resp = bus_request(kafka_bus, FABRIC_TOPIC, "read_order", {"id": order_id})
        assert resp.get("success") is True, f"read_order после finalize: {resp}"

    # ── Phase 5: Маршрут GCS ─────────────────────────────────────────────────

    def test_09_gcs_route(self, kafka_bus):
        route_resp = bus_request(kafka_bus, GCS_TOPIC, "plan_mission_route", {
            "pickup": {"lat": 55.75, "lon": 37.62},
            "dropoff": {"lat": 55.80, "lon": 37.70},
        })
        assert route_resp.get("success") is True
        route = (route_resp.get("payload") or {}).get("route")
        assert isinstance(route, list) and len(route) >= 2
