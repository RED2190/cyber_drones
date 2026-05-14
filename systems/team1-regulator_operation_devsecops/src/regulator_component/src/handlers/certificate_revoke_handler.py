# handlers/certificate_revoke_handler.py
import logging

from ..certificate_manager import CertificateManager
from ..broker_client import BrokerClient
from ..config import Config

logger = logging.getLogger(__name__)


class CertificateRevokeHandler:
    def __init__(self, cert_manager: CertificateManager, broker: BrokerClient):
        self.cert_manager = cert_manager
        self.broker = broker

    async def handle(self, message: dict):
        try:
            cert_id = message.get("certificate_id")
            reason = message.get("reason", "")
            if not cert_id:
                logger.warning("Revoke request missing certificate_id")
                return

            self.cert_manager.revoke_certificate(cert_id)

            response = {
                "certificate_id": cert_id,
                "revoked": True,
                "reason": reason
            }
            await self.broker.publish(Config.TOPIC_CERT_REVOKE_RESPONSE, response)
            logger.info(f"Revoked certificate {cert_id}")
        except Exception as e:
            logger.error(f"Error revoking certificate: {e}", exc_info=True)
