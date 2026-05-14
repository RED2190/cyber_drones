"""
Юнит-тесты для CertificateManager.
Проверяем: создание, верификацию, отзыв и получение сертификатов.
"""
import pytest
from datetime import datetime, timedelta


class TestCreateCertificate:
    def test_creates_certificate_with_correct_fields(self, tmp_cert_manager):
        cert = tmp_cert_manager.create_certificate(
            subject_type="firmware",
            subject_id="commit-abc123",
            security_goals=["FW-SEC-01", "FW-SEC-02"]
        )
        assert cert.certificate_id.startswith("CERT-FIRMWARE-")
        assert cert.subject_type == "firmware"
        assert cert.subject_id == "commit-abc123"
        assert cert.security_goals == ["FW-SEC-01", "FW-SEC-02"]
        assert cert.digital_signature is not None

    def test_certificate_saved_to_storage(self, tmp_cert_manager):
        cert = tmp_cert_manager.create_certificate(
            subject_type="drone",
            subject_id="SN-001",
            security_goals=["DRONE-AUTH"]
        )
        # Проверяем что сертификат попал в память
        assert cert.certificate_id in tmp_cert_manager.certificates

    def test_certificate_valid_for_365_days_by_default(self, tmp_cert_manager):
        cert = tmp_cert_manager.create_certificate(
            subject_type="operator",
            subject_id="op-001",
            security_goals=[]
        )
        delta = cert.valid_until - cert.issued_at
        assert delta.days == 365

    def test_certificate_custom_validity(self, tmp_cert_manager):
        cert = tmp_cert_manager.create_certificate(
            subject_type="firmware",
            subject_id="fw-001",
            security_goals=[],
            validity_days=30
        )
        delta = cert.valid_until - cert.issued_at
        assert delta.days == 30

    def test_two_certificates_have_unique_ids(self, tmp_cert_manager):
        cert1 = tmp_cert_manager.create_certificate("firmware", "fw-001", [])
        cert2 = tmp_cert_manager.create_certificate("firmware", "fw-002", [])
        assert cert1.certificate_id != cert2.certificate_id


class TestVerifyCertificate:
    def test_valid_certificate_passes(self, tmp_cert_manager):
        cert = tmp_cert_manager.create_certificate("drone", "SN-001", ["DRONE-AUTH"])
        assert tmp_cert_manager.verify_certificate(cert) is True

    def test_revoked_certificate_fails(self, tmp_cert_manager):
        cert = tmp_cert_manager.create_certificate("drone", "SN-002", [])
        tmp_cert_manager.revoke_certificate(cert.certificate_id)
        assert tmp_cert_manager.verify_certificate(cert) is False

    def test_tampered_signature_fails(self, tmp_cert_manager):
        cert = tmp_cert_manager.create_certificate("firmware", "fw-001", [])
        # Подменяем подпись
        cert.digital_signature = "tampered_signature_000"
        assert tmp_cert_manager.verify_certificate(cert) is False

    def test_expired_certificate_fails(self, tmp_cert_manager):
        cert = tmp_cert_manager.create_certificate("firmware", "fw-001", [], validity_days=1)
        # Сдвигаем valid_until в прошлое
        cert.valid_until = datetime.utcnow() - timedelta(days=1)
        assert tmp_cert_manager.verify_certificate(cert) is False


class TestRevokeCertificate:
    def test_revoke_adds_to_crl(self, tmp_cert_manager):
        cert = tmp_cert_manager.create_certificate("drone", "SN-001", [])
        tmp_cert_manager.revoke_certificate(cert.certificate_id)
        assert cert.certificate_id in tmp_cert_manager.crl

    def test_revoke_nonexistent_cert_does_not_raise(self, tmp_cert_manager):
        # Не должно падать с исключением
        tmp_cert_manager.revoke_certificate("CERT-NONEXISTENT-123")

    def test_revoke_twice_does_not_duplicate_in_crl(self, tmp_cert_manager):
        cert = tmp_cert_manager.create_certificate("drone", "SN-001", [])
        tmp_cert_manager.revoke_certificate(cert.certificate_id)
        tmp_cert_manager.revoke_certificate(cert.certificate_id)
        assert tmp_cert_manager.crl.count(cert.certificate_id) == 1


class TestGetCertificate:
    def test_returns_existing_certificate(self, tmp_cert_manager):
        cert = tmp_cert_manager.create_certificate("operator", "op-001", [])
        found = tmp_cert_manager.get_certificate(cert.certificate_id)
        assert found is not None
        assert found.certificate_id == cert.certificate_id

    def test_returns_none_for_missing_certificate(self, tmp_cert_manager):
        result = tmp_cert_manager.get_certificate("CERT-DOES-NOT-EXIST")
        assert result is None
