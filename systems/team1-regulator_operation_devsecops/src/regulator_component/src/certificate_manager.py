import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from pathlib import Path
import logging

from .models import Certificate

logger = logging.getLogger(__name__)


class CertificateManager:
    def __init__(self, cert_storage_path: str, crl_storage_path: str, private_key: str):
        self.cert_storage_path = Path(cert_storage_path)
        self.crl_storage_path = Path(crl_storage_path)
        self.private_key = private_key
        self.certificates: Dict[str, Certificate] = {}
        self.crl: List[str] = []
        self._load()

    def _load(self):
        if self.cert_storage_path.exists():
            with open(self.cert_storage_path) as f:
                data = json.load(f)
                for cert_data in data:
                    cert = Certificate(**cert_data)
                    self.certificates[cert.certificate_id] = cert

        if self.crl_storage_path.exists():
            with open(self.crl_storage_path) as f:
                self.crl = json.load(f)

    def _save(self):
        with open(self.cert_storage_path, 'w') as f:
            json.dump(
                [cert.model_dump() for cert in self.certificates.values()],
                f,
                default=str,
                indent = 2
            )

        with open(self.crl_storage_path, 'w') as f:
            json.dump(self.crl, f, indent = 2)

    def _normalize(self, data: dict) -> dict:
        """Приводим данные к одному виду (строки вместо datetime)."""
        normalized = {}
        for k, v in data.items():
            if isinstance(v, datetime):
                normalized[k] = v.isoformat()
            else:
                normalized[k] = v
        return normalized

    def _sign(self, data: dict) -> str:
        """Создаёт подпись."""
        normalized = self._normalize(data)
        data_str = json.dumps(normalized, sort_keys=True)
        return hashlib.sha256((data_str + self.private_key).encode()).hexdigest()

    def create_certificate(
        self,
        subject_type: str,
        subject_id: str,
        security_goals: List[str],
        validity_days: int = 365
    ) -> Certificate:

        cert_id = f"CERT-{subject_type.upper()}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{subject_id[-8:]}"
        issued_at = datetime.utcnow()
        valid_until = issued_at + timedelta(days=validity_days)

        cert_data = {
            "certificate_id": cert_id,
            "issued_at": issued_at.isoformat(),
            "valid_until": valid_until.isoformat(),
            "subject_type": subject_type,
            "subject_id": subject_id,
            "security_goals": security_goals,
        }

        cert_data["digital_signature"] = self._sign(cert_data)

        cert = Certificate(**cert_data)
        self.certificates[cert_id] = cert
        self._save()

        logger.info(f"Created certificate {cert_id}")
        return cert

    def verify_certificate(self, certificate: Certificate) -> bool:
        if certificate.certificate_id in self.crl:
            logger.warning(f"Certificate {certificate.certificate_id} is revoked")
            return False

        if not certificate.is_valid():
            logger.warning(f"Certificate {certificate.certificate_id} expired")
            return False

        cert_data = certificate.model_dump(exclude={'digital_signature'})
        expected_sig = self._sign(cert_data)

        if expected_sig != certificate.digital_signature:
            logger.warning(f"Certificate {certificate.certificate_id} signature mismatch")
            return False

        return True

    def revoke_certificate(self, cert_id: str):
        if cert_id in self.certificates:
            if cert_id not in self.crl:
                self.crl.append(cert_id)
                self._save()
                logger.info(f"Revoked certificate {cert_id}")
        else:
            logger.error(f"Certificate {cert_id} not found")

    def get_certificate(self, cert_id: str) -> Optional[Certificate]:
        return self.certificates.get(cert_id)