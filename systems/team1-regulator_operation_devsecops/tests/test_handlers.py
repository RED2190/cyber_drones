"""
Юнит-тесты для всех handlers.
Брокер замокан — проверяем только бизнес-логику и формат ответов.
"""
import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock


# ---------------------------------------------------------------------------
# FirmwareHandler
# ---------------------------------------------------------------------------

class TestFirmwareHandler:
    @pytest.fixture
    def handler(self, tmp_cert_manager, mock_broker):
        from src.regulator_component.src.handlers.firmware_handler import FirmwareHandler
        from src.regulator_component.src.security_test_runner import SecurityTestRunner
        from src.regulator_component.src.coverage_controller import CoverageController
        return FirmwareHandler(
            cert_manager=tmp_cert_manager,
            test_runner=SecurityTestRunner(mock=True),
            coverage_controller=CoverageController(mock=True),
            broker=mock_broker
        )

    @pytest.fixture
    def valid_message(self):
        return {
            "request_id": "req-fw-001",
            "timestamp": datetime.utcnow().isoformat(),
            "developer_id": "dev-team-01",
            "firmware": {"commit_hash": "abc123", "version": "1.0.0"},
            "drone_type": "quadcopter"
        }

    @pytest.mark.asyncio
    async def test_certified_firmware_publishes_result(self, handler, valid_message, mock_broker):
        await handler.handle(valid_message)
        mock_broker.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_certified_firmware_status_is_certified(self, handler, valid_message, mock_broker):
        await handler.handle(valid_message)
        topic, payload = mock_broker.publish.call_args[0]
        result = json.loads(payload)
        assert result["status"] == "CERTIFIED"

    @pytest.mark.asyncio
    async def test_certified_firmware_has_certificate(self, handler, valid_message, mock_broker):
        await handler.handle(valid_message)
        _, payload = mock_broker.publish.call_args[0]
        result = json.loads(payload)
        assert result["certificate"] is not None
        assert "certificate_id" in result["certificate"]

    @pytest.mark.asyncio
    async def test_request_id_preserved_in_response(self, handler, valid_message, mock_broker):
        await handler.handle(valid_message)
        _, payload = mock_broker.publish.call_args[0]
        result = json.loads(payload)
        assert result["request_id"] == "req-fw-001"

    @pytest.mark.asyncio
    async def test_invalid_json_string_does_not_raise(self, handler):
        # Не должно падать — просто логирует ошибку
        await handler.handle("not a json {{{")

    @pytest.mark.asyncio
    async def test_failed_security_test_produces_rejected(self, tmp_cert_manager, mock_broker):
        from src.regulator_component.src.handlers.firmware_handler import FirmwareHandler
        from src.regulator_component.src.coverage_controller import CoverageController

        failing_runner = MagicMock()
        failing_runner.run_tests = AsyncMock(return_value={"passed": False})

        handler = FirmwareHandler(tmp_cert_manager, failing_runner, CoverageController(mock=True), mock_broker)
        await handler.handle({
            "request_id": "req-fw-fail",
            "timestamp": datetime.utcnow().isoformat(),
            "developer_id": "dev-01",
            "firmware": {"commit_hash": "bad", "version": "0.0.1"},
            "drone_type": "quadcopter"
        })
        _, payload = mock_broker.publish.call_args[0]
        result = json.loads(payload)
        assert result["status"] == "REJECTED"
        assert result["certificate"] is None


# ---------------------------------------------------------------------------
# DroneHandler
# ---------------------------------------------------------------------------

class TestDroneHandler:
    @pytest.fixture
    def handler(self, tmp_cert_manager, mock_broker):
        from src.regulator_component.src.handlers.drone_handler import DroneHandler
        return DroneHandler(cert_manager=tmp_cert_manager, broker=mock_broker)

    @pytest.fixture
    def valid_firmware_cert_id(self, tmp_cert_manager):
        cert = tmp_cert_manager.create_certificate(
            subject_type="firmware",
            subject_id="commit-abc",
            security_goals=["FW-SEC-01"]
        )
        return cert.certificate_id

    @pytest.mark.asyncio
    async def test_approved_drone_with_valid_firmware_cert(self, handler, mock_broker, valid_firmware_cert_id):
        await handler.handle({
            "request_id": "req-drone-001",
            "timestamp": datetime.utcnow().isoformat(),
            "drone": {"model": "DJI Phantom", "serial_number": "SN-001", "manufacturer": "DJI"},
            "firmware": {"version": "1.0.0", "certificate_id": valid_firmware_cert_id}
        })
        _, payload = mock_broker.publish.call_args[0]
        result = json.loads(payload)
        assert result["status"] == "APPROVED"
        assert result["certificate"] is not None

    @pytest.mark.asyncio
    async def test_rejected_drone_without_firmware_cert(self, handler, mock_broker):
        await handler.handle({
            "request_id": "req-drone-002",
            "timestamp": datetime.utcnow().isoformat(),
            "drone": {"model": "DJI", "serial_number": "SN-002", "manufacturer": "DJI"},
            "firmware": {"version": "1.0.0"}  # нет certificate_id
        })
        _, payload = mock_broker.publish.call_args[0]
        result = json.loads(payload)
        assert result["status"] == "REJECTED"

    @pytest.mark.asyncio
    async def test_rejected_drone_with_nonexistent_firmware_cert(self, handler, mock_broker):
        await handler.handle({
            "request_id": "req-drone-003",
            "timestamp": datetime.utcnow().isoformat(),
            "drone": {"model": "DJI", "serial_number": "SN-003", "manufacturer": "DJI"},
            "firmware": {"version": "1.0.0", "certificate_id": "CERT-FAKE-999"}
        })
        _, payload = mock_broker.publish.call_args[0]
        result = json.loads(payload)
        assert result["status"] == "REJECTED"

    @pytest.mark.asyncio
    async def test_approved_drone_has_registration_number(self, handler, mock_broker, valid_firmware_cert_id):
        await handler.handle({
            "request_id": "req-drone-004",
            "timestamp": datetime.utcnow().isoformat(),
            "drone": {"model": "DJI", "serial_number": "SN-004", "manufacturer": "DJI"},
            "firmware": {"version": "1.0.0", "certificate_id": valid_firmware_cert_id}
        })
        _, payload = mock_broker.publish.call_args[0]
        result = json.loads(payload)
        assert result["drone"]["registration_number"].startswith("RU-BAS-")


# ---------------------------------------------------------------------------
# OperatorHandler
# ---------------------------------------------------------------------------

class TestOperatorHandler:
    @pytest.fixture
    def handler(self, tmp_cert_manager, mock_broker):
        from src.regulator_component.src.handlers.operator_handler import OperatorHandler
        return OperatorHandler(cert_manager=tmp_cert_manager, broker=mock_broker)

    @pytest.mark.asyncio
    async def test_operator_gets_certified(self, handler, mock_broker):
        await handler.handle({
            "timestamp": datetime.utcnow().isoformat(),
            "message_id": "msg-op-001",
            "operator_id": "op-001",
            "drone_id": "drone-001",
            "digital_signature": "sig-placeholder"
        })
        _, payload = mock_broker.publish.call_args[0]
        result = json.loads(payload)
        assert result["certificate_status"] == "certified"
        assert result["certificate_id"] is not None
        assert result["operator_id"] == "op-001"


# ---------------------------------------------------------------------------
# InsurerHandler
# ---------------------------------------------------------------------------

class TestInsurerHandler:
    @pytest.fixture
    def handler(self, mock_broker):
        from src.regulator_component.src.handlers.insurer_handler import InsurerHandler
        return InsurerHandler(broker=mock_broker)

    @pytest.mark.asyncio
    async def test_insurer_request_approved(self, handler, mock_broker):
        await handler.handle({
            "timestamp": datetime.utcnow().isoformat(),
            "message_id": "msg-ins-001",
            "insurer_id": "INS-001",
            "order_id": "order-001",
            "amount": 5000000.0,
            "incident_id": "inc-001"
        })
        _, payload = mock_broker.publish.call_args[0]
        result = json.loads(payload)
        assert result["approved"] is True
        assert result["message_id"] == "msg-ins-001"
        assert result["insurer_id"] == "INS-001"


# ---------------------------------------------------------------------------
# CertificateVerifyHandler
# ---------------------------------------------------------------------------

class TestCertificateVerifyHandler:
    @pytest.fixture
    def handler(self, tmp_cert_manager, mock_broker):
        from src.regulator_component.src.handlers.certificate_verify_handler import CertificateVerifyHandler
        return CertificateVerifyHandler(cert_manager=tmp_cert_manager, broker=mock_broker)

    @pytest.mark.asyncio
    async def test_valid_cert_returns_valid_true(self, handler, mock_broker, tmp_cert_manager):
        cert = tmp_cert_manager.create_certificate("drone", "SN-001", ["DRONE-AUTH"])
        await handler.handle({
            "request_id": "req-verify-001",
            "certificate_id": cert.certificate_id,
            "drone_id": "SN-001"
        })
        _, response = mock_broker.publish.call_args[0]
        result = response if isinstance(response, dict) else json.loads(response)
        assert result["valid"] is True
        assert result["status"] == "certified"

    @pytest.mark.asyncio
    async def test_nonexistent_cert_returns_invalid(self, handler, mock_broker):
        await handler.handle({
            "request_id": "req-verify-002",
            "certificate_id": "CERT-FAKE-000",
            "drone_id": "drone-x"
        })
        _, response = mock_broker.publish.call_args[0]
        result = response if isinstance(response, dict) else json.loads(response)
        assert result["valid"] is False
        assert result["status"] == "invalid"

    @pytest.mark.asyncio
    async def test_revoked_cert_returns_invalid(self, handler, mock_broker, tmp_cert_manager):
        cert = tmp_cert_manager.create_certificate("drone", "SN-002", [])
        tmp_cert_manager.revoke_certificate(cert.certificate_id)
        await handler.handle({
            "request_id": "req-verify-003",
            "certificate_id": cert.certificate_id,
            "drone_id": "SN-002"
        })
        _, response = mock_broker.publish.call_args[0]
        result = response if isinstance(response, dict) else json.loads(response)
        assert result["valid"] is False


# ---------------------------------------------------------------------------
# CertificateRevokeHandler
# ---------------------------------------------------------------------------

class TestCertificateRevokeHandler:
    @pytest.fixture
    def handler(self, tmp_cert_manager, mock_broker):
        from src.regulator_component.src.handlers.certificate_revoke_handler import CertificateRevokeHandler
        return CertificateRevokeHandler(cert_manager=tmp_cert_manager, broker=mock_broker)

    @pytest.mark.asyncio
    async def test_revoke_existing_cert(self, handler, mock_broker, tmp_cert_manager):
        cert = tmp_cert_manager.create_certificate("drone", "SN-001", [])
        await handler.handle({"certificate_id": cert.certificate_id, "reason": "stolen"})
        _, response = mock_broker.publish.call_args[0]
        assert response["revoked"] is True
        assert response["certificate_id"] == cert.certificate_id

    @pytest.mark.asyncio
    async def test_revoke_adds_to_crl(self, handler, tmp_cert_manager):
        cert = tmp_cert_manager.create_certificate("drone", "SN-002", [])
        await handler.handle({"certificate_id": cert.certificate_id, "reason": "test"})
        assert cert.certificate_id in tmp_cert_manager.crl

    @pytest.mark.asyncio
    async def test_missing_certificate_id_does_not_publish(self, handler, mock_broker):
        await handler.handle({"reason": "no cert id given"})
        mock_broker.publish.assert_not_called()
