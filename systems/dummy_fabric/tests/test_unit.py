"""Unit тесты для компонентов dummy_fabric (моки, без Fabric)."""
import json
import pytest
from unittest.mock import MagicMock, patch

from systems.dummy_fabric.src.cert_center.src.component import CertCenterComponent
from systems.dummy_fabric.src.aggregator.src.component import AggregatorComponent
from systems.dummy_fabric.src.insurer.src.component import InsurerComponent
from systems.dummy_fabric.src.operator_node.src.component import OperatorComponent
from systems.dummy_fabric.src.orvd.src.component import OrvdComponent
from systems.dummy_fabric.src.gateway.src.gateway import FabricGateway


def _mock_post(*args, **kwargs):
    """Подготавливает мок для requests.post."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"result": '{"ok": true}', "transaction_id": "tx1"}
    return resp


def _make_component(cls, component_id, component_type, topic):
    bus = MagicMock()
    with patch("systems.dummy_fabric.src._base.fabric_component.requests.post", side_effect=_mock_post):
        comp = cls(
            component_id=component_id,
            component_type=component_type,
            topic=topic,
            bus=bus,
            fabric_proxy_url="http://fake-proxy:3000",
        )
    return comp, bus


# ── CertCenter ─────────────────────────────────────────────────

class TestCertCenter:

    @pytest.fixture
    def cert_center(self):
        comp, bus = _make_component(
            CertCenterComponent, "test_cert_center", "cert_center",
            "components.fabric_cert_center",
        )
        return comp, bus

    def test_issue_type_certificate(self, cert_center):
        comp, _ = cert_center
        msg = {
            "action": "issue_type_certificate",
            "payload": {
                "id": "TC-001", "model": "X100",
                "manufacturer_id": "MFR-001",
                "hardware_objectives": '["obj1"]',
            },
        }
        with patch("systems.dummy_fabric.src._base.fabric_component.requests.post", side_effect=_mock_post) as mock:
            result = comp._handle_issue_type_cert(msg)
            call_payload = mock.call_args[1]["json"]
            assert call_payload["method"] == "DronePropertiesContract:IssueTypeCertificate"
            assert call_payload["args"][0] == "TC-001"

    def test_certify_firmware(self, cert_center):
        comp, _ = cert_center
        msg = {
            "action": "certify_firmware",
            "payload": {
                "id": "FW-001",
                "security_objectives": '["sec1"]',
                "software_objectives": '["sw1"]',
                "certified_at": "2025-01-01",
                "certified_by": "CertOrg",
            },
        }
        with patch("systems.dummy_fabric.src._base.fabric_component.requests.post", side_effect=_mock_post) as mock:
            comp._handle_certify_firmware(msg)
            call_payload = mock.call_args[1]["json"]
            assert call_payload["method"] == "FirmwareContract:CertifyFirmware"

    def test_create_drone_pass(self, cert_center):
        comp, _ = cert_center
        msg = {
            "action": "create_drone_pass",
            "payload": {
                "id": "DP-001", "developer_id": "DEV-001",
                "model": "X100", "drone_type": "multirotor",
                "weight_kg": 2.5, "max_flight_range_km": 10,
                "max_payload_weight_kg": 0.5, "release_year": 2024,
                "firmware_id": "FW-001", "type_certificate_id": "TC-001",
            },
        }
        with patch("systems.dummy_fabric.src._base.fabric_component.requests.post", side_effect=_mock_post) as mock:
            comp._handle_create_drone_pass(msg)
            call_payload = mock.call_args[1]["json"]
            assert call_payload["method"] == "DronePropertiesContract:CreateDronePass"
            assert len(call_payload["args"]) == 10

    def test_read_drone_pass(self, cert_center):
        comp, _ = cert_center
        msg = {"action": "read_drone_pass", "payload": {"id": "DP-001"}}
        with patch("systems.dummy_fabric.src._base.fabric_component.requests.post", side_effect=_mock_post) as mock:
            comp._handle_read_drone_pass(msg)
            call_payload = mock.call_args[1]["json"]
            assert call_payload["method"] == "DronePropertiesContract:ReadDronePass"
            assert "/query" in mock.call_args[0][0]


# ── Aggregator ─────────────────────────────────────────────────

class TestAggregator:

    @pytest.fixture
    def aggregator(self):
        comp, bus = _make_component(
            AggregatorComponent, "test_aggregator", "aggregator",
            "components.fabric_aggregator",
        )
        return comp, bus

    def test_create_order(self, aggregator):
        comp, _ = aggregator
        msg = {
            "action": "create_order",
            "payload": {
                "id": "ORD-001", "aggregator_id": "AGG-1",
                "operator_id": "", "drone_id": "",
                "insurer_id": "INS-1", "cert_center_id": "CC-1",
                "developer_id": "DEV-1", "fleet_price": 100,
                "aggregator_fee": 10, "insurance_premium": 5,
                "risk_reserve": 2, "insurance_coverage_amount": 1000,
                "mission_insurance_id": "MI-001",
                "details": "[]",
            },
        }
        with patch("systems.dummy_fabric.src._base.fabric_component.requests.post", side_effect=_mock_post) as mock:
            comp._handle_create_order(msg)
            call_payload = mock.call_args[1]["json"]
            assert call_payload["method"] == "OrderContract:CreateOrder"

    def test_assign_order(self, aggregator):
        comp, _ = aggregator
        msg = {
            "action": "assign_order",
            "payload": {
                "order_id": "ORD-001",
                "operator_id": "OP-1",
                "drone_id": "DP-001",
                "details": "[]",
            },
        }
        with patch("systems.dummy_fabric.src._base.fabric_component.requests.post", side_effect=_mock_post) as mock:
            comp._handle_assign_order(msg)
            call_payload = mock.call_args[1]["json"]
            assert call_payload["method"] == "OrderContract:AssignOrder"

    def test_request_flight_permission(self, aggregator):
        comp, _ = aggregator
        msg = {
            "action": "request_flight_permission",
            "payload": {
                "order_id": "ORD-001",
                "valid_from": "2025-01-01T00:00:00Z",
                "valid_to": "2025-01-02T00:00:00Z",
            },
        }
        with patch("systems.dummy_fabric.src._base.fabric_component.requests.post", side_effect=_mock_post) as mock:
            comp._handle_request_fp(msg)
            call_payload = mock.call_args[1]["json"]
            assert call_payload["method"] == "OrderContract:RequestFlightPermission"

    def test_read_order(self, aggregator):
        comp, _ = aggregator
        msg = {"action": "read_order", "payload": {"id": "ORD-001"}}
        with patch("systems.dummy_fabric.src._base.fabric_component.requests.post", side_effect=_mock_post) as mock:
            comp._handle_read_order(msg)
            assert "/query" in mock.call_args[0][0]


# ── Insurer ────────────────────────────────────────────────────

class TestInsurer:

    @pytest.fixture
    def insurer(self):
        comp, bus = _make_component(
            InsurerComponent, "test_insurer", "insurer",
            "components.fabric_insurer",
        )
        return comp, bus

    def test_create_insurance(self, insurer):
        comp, _ = insurer
        msg = {
            "action": "create_insurance",
            "payload": {
                "drone_id": "DP-001", "insurer_id": "INS-1",
                "coverage_amount": 1000, "incident_count": 0,
                "valid_from": "2025-01-01", "valid_to": "2026-01-01",
            },
        }
        with patch("systems.dummy_fabric.src._base.fabric_component.requests.post", side_effect=_mock_post) as mock:
            comp._handle_create_insurance(msg)
            call_payload = mock.call_args[1]["json"]
            assert call_payload["method"] == "DronePropertiesContract:CreateInsuranceRecord"

    def test_approve_order(self, insurer):
        comp, _ = insurer
        msg = {"action": "approve_order", "payload": {"order_id": "ORD-001"}}
        with patch("systems.dummy_fabric.src._base.fabric_component.requests.post", side_effect=_mock_post) as mock:
            comp._handle_approve_order(msg)
            call_payload = mock.call_args[1]["json"]
            assert call_payload["method"] == "OrderContract:ApproveOrder"


# ── Operator ───────────────────────────────────────────────────

class TestOperator:

    @pytest.fixture
    def operator(self):
        comp, bus = _make_component(
            OperatorComponent, "test_operator", "operator",
            "components.fabric_operator",
        )
        return comp, bus

    def test_confirm_order(self, operator):
        comp, _ = operator
        msg = {"action": "confirm_order", "payload": {"order_id": "ORD-001"}}
        with patch("systems.dummy_fabric.src._base.fabric_component.requests.post", side_effect=_mock_post) as mock:
            comp._handle_confirm_order(msg)
            call_payload = mock.call_args[1]["json"]
            assert call_payload["method"] == "OrderContract:ConfirmOrder"

    def test_start_order(self, operator):
        comp, _ = operator
        msg = {"action": "start_order", "payload": {"order_id": "ORD-001"}}
        with patch("systems.dummy_fabric.src._base.fabric_component.requests.post", side_effect=_mock_post) as mock:
            comp._handle_start_order(msg)
            call_payload = mock.call_args[1]["json"]
            assert call_payload["method"] == "OrderContract:StartOrder"

    def test_finish_order(self, operator):
        comp, _ = operator
        msg = {"action": "finish_order", "payload": {"order_id": "ORD-001"}}
        with patch("systems.dummy_fabric.src._base.fabric_component.requests.post", side_effect=_mock_post) as mock:
            comp._handle_finish_order(msg)
            call_payload = mock.call_args[1]["json"]
            assert call_payload["method"] == "OrderContract:FinishOrder"


# ── Orvd ───────────────────────────────────────────────────────

class TestOrvd:

    @pytest.fixture
    def orvd(self):
        comp, bus = _make_component(
            OrvdComponent, "test_orvd", "orvd",
            "components.fabric_orvd",
        )
        return comp, bus

    def test_approve_flight_permission(self, orvd):
        comp, _ = orvd
        msg = {
            "action": "approve_flight_permission",
            "payload": {"permission_id": "PERM-ORD-001"},
        }
        with patch("systems.dummy_fabric.src._base.fabric_component.requests.post", side_effect=_mock_post) as mock:
            comp._handle_approve_fp(msg)
            call_payload = mock.call_args[1]["json"]
            assert call_payload["method"] == "OrderContract:ApproveFlightPermission"
            assert call_payload["args"][0] == "PERM-ORD-001"


# ── Gateway Routing ────────────────────────────────────────────

class TestGateway:

    @pytest.fixture
    def gateway(self):
        bus = MagicMock()
        gw = FabricGateway(system_id="test_gw", bus=bus)
        return gw, bus

    def test_routes_create_order_to_aggregator(self, gateway):
        gw, bus = gateway
        bus.request.return_value = {
            "success": True,
            "payload": {"ok": True},
        }
        msg = {
            "action": "create_order",
            "sender": "external",
            "payload": {"id": "ORD-001"},
        }
        result = gw._handle_proxy(msg)
        bus.request.assert_called_once()
        target_topic = bus.request.call_args[0][0]
        assert "aggregator" in target_topic

    def test_routes_create_drone_pass_to_cert_center(self, gateway):
        gw, bus = gateway
        bus.request.return_value = {
            "success": True,
            "payload": {"ok": True},
        }
        msg = {
            "action": "create_drone_pass",
            "sender": "external",
            "payload": {"id": "DP-001"},
        }
        result = gw._handle_proxy(msg)
        target_topic = bus.request.call_args[0][0]
        assert "cert_center" in target_topic

    def test_routes_approve_order_to_insurer(self, gateway):
        gw, bus = gateway
        bus.request.return_value = {
            "success": True,
            "payload": {"ok": True},
        }
        msg = {
            "action": "approve_order",
            "sender": "external",
            "payload": {"order_id": "ORD-001"},
        }
        gw._handle_proxy(msg)
        target_topic = bus.request.call_args[0][0]
        assert "insurer" in target_topic

    def test_routes_confirm_order_to_operator(self, gateway):
        gw, bus = gateway
        bus.request.return_value = {
            "success": True,
            "payload": {"ok": True},
        }
        msg = {
            "action": "confirm_order",
            "sender": "external",
            "payload": {"order_id": "ORD-001"},
        }
        gw._handle_proxy(msg)
        target_topic = bus.request.call_args[0][0]
        assert "operator" in target_topic

    def test_routes_approve_fp_to_orvd(self, gateway):
        gw, bus = gateway
        bus.request.return_value = {
            "success": True,
            "payload": {"ok": True},
        }
        msg = {
            "action": "approve_flight_permission",
            "sender": "external",
            "payload": {"permission_id": "PERM-001"},
        }
        gw._handle_proxy(msg)
        target_topic = bus.request.call_args[0][0]
        assert "orvd" in target_topic

    def test_timeout_returns_error(self, gateway):
        gw, bus = gateway
        bus.request.return_value = None
        msg = {
            "action": "create_order",
            "sender": "external",
            "payload": {},
        }
        result = gw._handle_proxy(msg)
        assert "error" in result

    def test_all_actions_have_routes(self, gateway):
        gw, _ = gateway
        expected_actions = [
            "issue_type_certificate", "certify_firmware",
            "create_drone_pass", "read_drone_pass", "list_drone_passes",
            "create_insurance", "read_insurance", "approve_order",
            "create_order", "assign_order", "read_order",
            "request_flight_permission", "finalize_order",
            "confirm_order", "start_order", "finish_order",
            "approve_flight_permission",
        ]
        for action in expected_actions:
            assert action in gw.ACTION_ROUTING, f"Missing route for {action}"
