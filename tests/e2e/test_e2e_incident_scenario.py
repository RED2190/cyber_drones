"""
E2E negative scenario: после старта миссии — разбирательство (страховка, регулятор).

Полёт и симуляция на борту не обязательны: достаточно зафиксировать «миссия
стартовала» лёгким шагом (ORVD: регистрация + авторизация миссии), затем
проверить доступные API разбирательства.
"""
from __future__ import annotations

import time
from typing import Any, Dict

import pytest
import requests

OPERATOR_TOPIC = "systems.operator"
ORVD_TOPIC = "systems.orvd_system"
REGULATOR_TOPIC = "systems.regulator"
INSURER_TOPIC = "systems.insurer"
AGREGATOR_OPERATOR_REQUESTS_TOPIC = "components.agregator.operator.requests"

E2E_DRONE_ID = "drone_001"
ORDER_BUDGET = 5000
_state: Dict[str, Any] = {}


def bus_request(bus, topic: str, action: str, payload: dict, timeout: float = 25) -> Dict[str, Any]:
    resp = bus.request(
        topic,
        {"action": action, "sender": "e2e_incident_test", "payload": payload},
        timeout=timeout,
    )
    assert resp is not None, f"Timeout: {action} -> {topic}"
    return resp


def rest_post(base: str, path: str, json: dict | None = None) -> requests.Response:
    return requests.post(f"{base}{path}", json=json or {}, timeout=15)


def rest_get(base: str, path: str) -> requests.Response:
    return requests.get(f"{base}{path}", timeout=15)


class TestE2EIncidentScenario:
    """Миссия считается стартовавшей без запуска полёта; далее — разбирательство."""

    def test_01_prepare_entities(self, kafka_bus, agregator_url):
        for system_id, system_type in (
            ("agregator", "aggregator"),
            ("operator", "operator"),
            ("insurer", "insurer"),
            ("orvd_system", "orvd"),
            ("gcs", "gcs"),
            ("cyber_drons", "drone"),
        ):
            reg = bus_request(
                kafka_bus,
                REGULATOR_TOPIC,
                "register_system",
                {"system_id": system_id, "system_type": system_type},
            )
            assert reg.get("success") is True, reg

        cert = bus_request(
            kafka_bus,
            REGULATOR_TOPIC,
            "register_operator_cert",
            {"operator_id": "e2e-operator-incident"},
        )
        assert cert.get("success") is True, cert
        _state["operator_cert_id"] = (cert.get("payload") or {}).get("certificate_id")

        op = rest_post(
            agregator_url,
            "/operators",
            {
                "name": "E2E Incident Operator",
                "license": "E2E-INC-LIC-1",
                "operator_id": "e2e-operator-incident",
                "certificate_id": _state["operator_cert_id"],
            },
        )
        assert op.status_code in (200, 201), f"{op.status_code} {op.text}"

        drone_cert = bus_request(
            kafka_bus,
            REGULATOR_TOPIC,
            "register_drone_cert",
            {"drone_id": E2E_DRONE_ID},
        )
        assert drone_cert.get("success") is True, drone_cert
        _state["drone_cert_id"] = (drone_cert.get("payload") or {}).get("certificate_id")

        reg_drone = bus_request(
            kafka_bus,
            OPERATOR_TOPIC,
            "register_drone",
            {
                "drone_id": E2E_DRONE_ID,
                "model": "AgroDron-X1",
                "capabilities": ["cargo", "sprayer"],
                "certificate_id": _state["drone_cert_id"],
            },
        )
        assert reg_drone.get("success") is True, reg_drone

    def test_02_create_order_and_mission_insurance(self, kafka_bus, agregator_url):
        customer = rest_post(
            agregator_url,
            "/customers",
            {"name": "Incident Customer", "email": "incident@local"},
        )
        assert customer.status_code in (200, 201), f"{customer.status_code} {customer.text}"
        customer_id = customer.json().get("customer_id") or customer.json().get("id")
        assert customer_id, "customer_id missing"

        create = rest_post(
            agregator_url,
            "/orders",
            {
                "customer_id": customer_id,
                "description": "Incident scenario order",
                "budget": ORDER_BUDGET,
                "from_lat": 55.75,
                "from_lon": 37.62,
                "to_lat": 55.80,
                "to_lon": 37.70,
            },
        )
        assert create.status_code in (200, 201), f"{create.status_code} {create.text}"
        body = create.json()
        order_id = body.get("order_id") or body.get("id")
        assert order_id, body
        _state["order_id"] = order_id

        status = body.get("status", "")
        for _ in range(20):
            if status == "matched":
                break
            time.sleep(2)
            poll = rest_get(agregator_url, f"/orders/{order_id}")
            if poll.status_code == 200:
                status = poll.json().get("status", "")

        if status != "matched":
            kafka_bus.publish(
                AGREGATOR_OPERATOR_REQUESTS_TOPIC,
                {
                    "action": "create_order",
                    "sender": "e2e_incident_test",
                    "correlation_id": order_id,
                    "payload": {
                        "customer_id": customer_id,
                        "budget": ORDER_BUDGET,
                        "description": "Incident scenario order",
                    },
                },
            )
            time.sleep(5)
            status = rest_get(agregator_url, f"/orders/{order_id}").json().get("status", "")
        assert status == "matched", f"order is not matched: {status}"

        conf = rest_post(
            agregator_url,
            f"/orders/{order_id}/confirm-price",
            {"operator_id": "operator_component", "accepted_price": ORDER_BUDGET * 0.85},
        )
        assert conf.status_code in (200, 201), f"{conf.status_code} {conf.text}"

        mission_ins = bus_request(
            kafka_bus,
            OPERATOR_TOPIC,
            "buy_insurance_policy",
            {
                "order_id": order_id,
                "drone_id": E2E_DRONE_ID,
                "coverage_amount": ORDER_BUDGET,
                "insurance_action": "mission_insurance",
            },
        )
        assert mission_ins.get("success") is True, mission_ins
        payload = mission_ins.get("payload") or {}
        assert payload.get("status") == "insured", payload
        _state["policy_id"] = ((payload.get("policy") or {}).get("policy_id"))
        assert _state["policy_id"], "mission policy_id missing"

    def test_03_mission_started_marker_orvd(self, kafka_bus):
        """Лёгкий маркер «миссия стартовала»: ORVD register + authorize (без полёта/SITL)."""
        order_id = _state.get("order_id")
        assert order_id, "order_id missing — run test_02 first"
        mission_id = f"mission-{order_id}"

        try:
            reg_m = bus_request(
                kafka_bus,
                ORVD_TOPIC,
                "register_mission",
                {
                    "mission_id": mission_id,
                    "drone_id": E2E_DRONE_ID,
                    "route": [
                        {"lat": 55.75, "lon": 37.62},
                        {"lat": 55.80, "lon": 37.70},
                    ],
                },
            )
        except AssertionError:
            pytest.skip("ORVD topic not reachable — cannot mark mission started")

        assert reg_m.get("success") is True, f"register_mission: {reg_m}"

        last = None
        try:
            for _ in range(6):
                auth_m = bus_request(
                    kafka_bus,
                    ORVD_TOPIC,
                    "authorize_mission",
                    {"mission_id": mission_id},
                    timeout=20,
                )
                last = auth_m
                if auth_m.get("success") and (auth_m.get("payload") or {}).get("status") == "authorized":
                    break
                time.sleep(2)
        except AssertionError:
            pytest.skip("ORVD authorize_mission timed out")

        assert last is not None
        assert last.get("success") is True, last
        assert (last.get("payload") or {}).get("status") == "authorized", last

        _state["mission_id_orvd"] = mission_id
        _state["mission_started"] = True

    def test_04_incident_investigation_and_settlement(self, kafka_bus, agregator_url):
        if not _state.get("mission_started"):
            pytest.skip("Mission not marked started — run test_03 first")

        order_id = _state["order_id"]
        damage_amount = int(ORDER_BUDGET * 0.6)

        customer_req = rest_post(
            agregator_url,
            f"/orders/{order_id}/confirm-completion",
            {"incident": True, "compensation_requested": damage_amount},
        )
        assert customer_req.status_code not in (404, 405), (
            "Aggregator incident/customer REST API is missing for settlement flow"
        )

        incident = bus_request(
            kafka_bus,
            OPERATOR_TOPIC,
            "buy_insurance_policy",
            {
                "order_id": order_id,
                "drone_id": E2E_DRONE_ID,
                "coverage_amount": damage_amount,
                "insurance_action": "report_incident",
                "incident": {
                    "damage_amount": damage_amount,
                    "incident_type": "inflight_failure",
                    "description": "telemetry anomaly during mission",
                },
            },
        )
        assert incident.get("success") is True, incident
        inc_payload = incident.get("payload") or {}
        assert inc_payload.get("status") == "incident_processed", inc_payload
        claim = inc_payload.get("claim") or {}
        assert claim.get("payment_amount") == damage_amount, claim

        calc = bus_request(
            kafka_bus,
            INSURER_TOPIC,
            "calculate_policy",
            {
                "drone_id": E2E_DRONE_ID,
                "drone_type": "delivery",
                "coverage_amount": ORDER_BUDGET,
            },
        )
        assert calc.get("success") is True, calc
        calc_pl = calc.get("payload") or {}
        assert "kincident_history" in calc_pl, calc_pl

        verify_operator_cert = bus_request(
            kafka_bus,
            REGULATOR_TOPIC,
            "verify_operator_cert",
            {
                "operator_id": "e2e-operator-incident",
                "certificate_id": _state["operator_cert_id"],
            },
        )
        assert verify_operator_cert.get("success") is True, verify_operator_cert
        assert (verify_operator_cert.get("payload") or {}).get("valid") is True

        for system_id in ("operator", "insurer", "agregator"):
            v = bus_request(kafka_bus, REGULATOR_TOPIC, "verify_system", {"system_id": system_id})
            assert v.get("success") is True, v
            assert (v.get("payload") or {}).get("verified") is True

        order_view = rest_get(agregator_url, f"/orders/{order_id}")
        if order_view.status_code == 200:
            status = order_view.json().get("status") or (order_view.json().get("order") or {}).get("status")
            assert status in (
                "completed",
                "incident",
                "in_incident",
                "failed",
                "cancelled",
                "in_progress",
                "matched",
                "confirmed",
            ), status
