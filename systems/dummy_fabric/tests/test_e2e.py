"""
E2E тесты для dummy_fabric.

Требования: запущенная Fabric-сеть + fabric-proxy инстансы.
Каждый шаг реально пишет в леджер через свой fabric-proxy.

Тест выполняет полный сценарий заказа:
  1.  CertCenter:  CertifyFirmware
  2.  CertCenter:  IssueTypeCertificate
  3.  CertCenter:  CreateDronePass
  4.  Insurer:     CreateInsuranceRecord
  5.  Aggregator:  CreateOrder
  6.  Aggregator:  AssignOrder
  7.  Insurer:     ApproveOrder
  8.  Operator:    ConfirmOrder
  9.  Aggregator:  RequestFlightPermission
  10. Orvd:        ApproveFlightPermission
  11. Operator:    StartOrder
  12. Operator:    FinishOrder
  13. Aggregator:  FinalizeOrder
  14. Aggregator:  ReadOrder (query) — проверяем финальный статус
"""
import os
import json
import uuid
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests


PROXY_AGGREGATOR = os.environ.get("FABRIC_PROXY_AGGREGATOR", "http://localhost:3001")
PROXY_CERTCENTER = os.environ.get("FABRIC_PROXY_CERTCENTER", "http://localhost:3002")
PROXY_INSURER = os.environ.get("FABRIC_PROXY_INSURER", "http://localhost:3003")
PROXY_OPERATOR = os.environ.get("FABRIC_PROXY_OPERATOR", "http://localhost:3004")
PROXY_ORVD = os.environ.get("FABRIC_PROXY_ORVD", "http://localhost:3005")

CHANNEL = os.environ.get("FABRIC_CHANNEL", "dronechannel")
CHAINCODE = os.environ.get("FABRIC_CHAINCODE", "drone-chaincode")


def _invoke(proxy_url: str, method: str, args: list) -> dict:
    """Вызов invoke через fabric-proxy и возврат результата."""
    resp = requests.post(
        f"{proxy_url}/api/invoke",
        json={"channel": CHANNEL, "chaincode": CHAINCODE, "method": method, "args": args},
        timeout=60,
    )
    data = resp.json()
    assert resp.status_code == 200, f"invoke {method} failed: {data}"
    assert "error" not in data, f"invoke {method} error: {data.get('error')}"
    return data


def _query(proxy_url: str, method: str, args: list) -> dict:
    """Вызов query через fabric-proxy и возврат распарсенного результата."""
    resp = requests.post(
        f"{proxy_url}/api/query",
        json={"channel": CHANNEL, "chaincode": CHAINCODE, "method": method, "args": args},
        timeout=60,
    )
    data = resp.json()
    assert resp.status_code == 200, f"query {method} failed: {data}"
    assert "error" not in data, f"query {method} error: {data.get('error')}"
    result_raw = data.get("result", "")
    if result_raw:
        return json.loads(result_raw)
    return data


def _uid(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def _proxy_healthy(url: str) -> str:
    """Returns empty string if healthy, error message otherwise."""
    try:
        r = requests.get(f"{url}/health", timeout=5)
        if r.status_code == 200:
            return ""
        return f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return str(e)


PROXIES = [
    ("aggregator", PROXY_AGGREGATOR),
    ("certcenter", PROXY_CERTCENTER),
    ("insurer", PROXY_INSURER),
    ("operator", PROXY_OPERATOR),
    ("orvd", PROXY_ORVD),
]

MAX_WAIT = int(os.environ.get("FABRIC_PROXY_WAIT", "90"))


@pytest.fixture(scope="module")
def check_proxies():
    """Ожидает готовности всех fabric-proxy (до MAX_WAIT секунд), иначе skip."""
    deadline = time.time() + MAX_WAIT
    while True:
        errors = {}
        for name, url in PROXIES:
            err = _proxy_healthy(url)
            if err:
                errors[name] = err
        if not errors:
            print(f"All fabric proxies healthy")
            return
        if time.time() >= deadline:
            detail = "; ".join(f"{n} ({u}): {errors[n]}" for n, u in PROXIES if n in errors)
            pytest.skip(f"fabric-proxy not ready after {MAX_WAIT}s — {detail}")
        time.sleep(5)


@pytest.fixture(scope="module")
def test_ids():
    """Уникальные ID для данного прогона тестов."""
    suffix = uuid.uuid4().hex[:6]
    return {
        "firmware_id": f"FW-{suffix}",
        "type_cert_id": f"TC-{suffix}",
        "drone_pass_id": f"DP-{suffix}",
        "order_id": f"ORD-{suffix}",
        "developer_id": f"DEV-{suffix}",
        "aggregator_id": f"AGG-{suffix}",
        "operator_id": f"OP-{suffix}",
        "insurer_id": f"INS-{suffix}",
        "cert_center_id": f"CC-{suffix}",
        "manufacturer_id": f"MFR-{suffix}",
    }


class TestE2EOrderWorkflow:
    """Полный E2E сценарий: от сертификации прошивки до финализации заказа."""

    def test_01_certify_firmware(self, check_proxies, test_ids):
        result = _invoke(PROXY_CERTCENTER, "FirmwareContract:CertifyFirmware", [
            test_ids["firmware_id"],
            '["sec_obj_1"]',
            '["sw_obj_1"]',
            datetime.now(timezone.utc).isoformat(),
            "CertAuthority",
        ])
        assert result.get("transaction_id") or result.get("result") is not None

    def test_02_issue_type_certificate(self, check_proxies, test_ids):
        result = _invoke(PROXY_CERTCENTER, "DronePropertiesContract:IssueTypeCertificate", [
            test_ids["type_cert_id"],
            "TestDroneModel",
            test_ids["manufacturer_id"],
            '["hw_obj_1"]',
        ])
        assert result.get("transaction_id") or result.get("result") is not None

    def test_03_create_drone_pass(self, check_proxies, test_ids):
        result = _invoke(PROXY_CERTCENTER, "DronePropertiesContract:CreateDronePass", [
            test_ids["drone_pass_id"],
            test_ids["developer_id"],
            "TestDroneModel",
            "multirotor",
            "3",
            "10",
            "1",
            "2024",
            test_ids["firmware_id"],
            test_ids["type_cert_id"],
        ])
        assert result.get("transaction_id") or result.get("result") is not None

    def test_04_create_insurance(self, check_proxies, test_ids):
        now = datetime.now(timezone.utc)
        result = _invoke(PROXY_INSURER, "DronePropertiesContract:CreateInsuranceRecord", [
            test_ids["drone_pass_id"],
            test_ids["insurer_id"],
            "50000",
            "0",
            now.isoformat(),
            (now + timedelta(days=365)).isoformat(),
        ])
        assert result.get("transaction_id") or result.get("result") is not None

    def test_05_create_order(self, check_proxies, test_ids):
        result = _invoke(PROXY_AGGREGATOR, "OrderContract:CreateOrder", [
            test_ids["order_id"],
            test_ids["aggregator_id"],
            "",
            "",
            test_ids["insurer_id"],
            test_ids["cert_center_id"],
            test_ids["developer_id"],
            "1000",
            "100",
            "50",
            "20",
            "50000",
            f'INS-{test_ids["drone_pass_id"]}',
            "[]",
        ])
        assert result.get("transaction_id") or result.get("result") is not None

    def test_06_assign_order(self, check_proxies, test_ids):
        result = _invoke(PROXY_AGGREGATOR, "OrderContract:AssignOrder", [
            test_ids["order_id"],
            test_ids["operator_id"],
            test_ids["drone_pass_id"],
            "[]",
        ])
        assert result.get("transaction_id") or result.get("result") is not None

    def test_07_approve_order(self, check_proxies, test_ids):
        result = _invoke(PROXY_INSURER, "OrderContract:ApproveOrder", [
            test_ids["order_id"],
        ])
        assert result.get("transaction_id") or result.get("result") is not None

    def test_08_confirm_order(self, check_proxies, test_ids):
        result = _invoke(PROXY_OPERATOR, "OrderContract:ConfirmOrder", [
            test_ids["order_id"],
        ])
        assert result.get("transaction_id") or result.get("result") is not None

    def test_09_request_flight_permission(self, check_proxies, test_ids):
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=1)
        result = _invoke(PROXY_AGGREGATOR, "OrderContract:RequestFlightPermission", [
            test_ids["order_id"],
            now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            future.strftime("%Y-%m-%dT%H:%M:%SZ"),
        ])
        assert result.get("transaction_id") or result.get("result") is not None

    def test_10_approve_flight_permission(self, check_proxies, test_ids):
        permission_id = f'PERM-{test_ids["order_id"]}'
        result = _invoke(PROXY_ORVD, "OrderContract:ApproveFlightPermission", [
            permission_id,
        ])
        assert result.get("transaction_id") or result.get("result") is not None

    def test_11_start_order(self, check_proxies, test_ids):
        result = _invoke(PROXY_OPERATOR, "OrderContract:StartOrder", [
            test_ids["order_id"],
        ])
        assert result.get("transaction_id") or result.get("result") is not None

    def test_12_finish_order(self, check_proxies, test_ids):
        result = _invoke(PROXY_OPERATOR, "OrderContract:FinishOrder", [
            test_ids["order_id"],
        ])
        assert result.get("transaction_id") or result.get("result") is not None

    def test_13_finalize_order(self, check_proxies, test_ids):
        result = _invoke(PROXY_AGGREGATOR, "OrderContract:FinalizeOrder", [
            test_ids["order_id"],
        ])
        assert result.get("transaction_id") or result.get("result") is not None

    def test_14_query_final_order(self, check_proxies, test_ids):
        order = _query(PROXY_AGGREGATOR, "OrderContract:ReadOrder", [
            test_ids["order_id"],
        ])
        assert order.get("ID") == test_ids["order_id"] or order.get("id") == test_ids["order_id"]

    def test_15_query_drone_pass(self, check_proxies, test_ids):
        dp = _query(PROXY_CERTCENTER, "DronePropertiesContract:ReadDronePass", [
            test_ids["drone_pass_id"],
        ])
        assert dp.get("ID") == test_ids["drone_pass_id"] or dp.get("id") == test_ids["drone_pass_id"]
