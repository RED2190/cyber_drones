import pytest
import tempfile
import json
import os
import sys

# Добавляем корень проекта в sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.regulator_component.src.certificate_manager import CertificateManager
from src.regulator_component.src.broker_client import BrokerClient


@pytest.fixture
def tmp_cert_manager(tmp_path):
    """CertificateManager с временными файлами — не трогает реальные certificates.json."""
    cert_file = tmp_path / "certificates.json"
    crl_file = tmp_path / "crl.json"
    cert_file.write_text("[]")
    crl_file.write_text("[]")
    return CertificateManager(
        cert_storage_path=str(cert_file),
        crl_storage_path=str(crl_file),
        private_key="test_private_key"
    )


@pytest.fixture
def mock_broker(mocker):
    """BrokerClient с замоканным publish — перехватывает все исходящие сообщения."""
    broker = BrokerClient(url="amqp://localhost", exchange="test")
    broker.publish = mocker.AsyncMock()
    return broker
