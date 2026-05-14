# handlers/certificate_verify_handler.py
import logging
import json

from ..certificate_manager import CertificateManager
from ..broker_client import BrokerClient
from ..config import Config

logger = logging.getLogger(__name__)


class CertificateVerifyHandler:
    def __init__(self, cert_manager: CertificateManager, broker: BrokerClient):
        self.cert_manager = cert_manager
        self.broker = broker

    async def handle(self, message: dict):
        try:
            if isinstance(message, str):
                message = json.loads(message)

            request_id = message.get("request_id")
            payload = message.get("payload", {})
            cert_id = payload.get("certificate_id") or message.get("certificate_id")
            drone_id = payload.get("drone_id") or message.get("drone_id", "unknown")

            valid = False
            details = None
            if cert_id:
                cert = self.cert_manager.get_certificate(cert_id)
                if cert:
                    valid = self.cert_manager.verify_certificate(cert)
                    details = cert.model_dump() if valid else None

            response = {
                "request_id": request_id,
                "drone_id": drone_id,
                "certificate_id": cert_id,
                "valid": valid,
                "status": "certified" if valid else "invalid",
                "details": details
            }

            await self.broker.publish(Config.TOPIC_CERT_VERIFY_RESPONSE, response)
            logger.info(f"Verification for cert {cert_id}: {valid}")
        except Exception as e:
            logger.error(f"Error verifying certificate: {e}", exc_info=True)
