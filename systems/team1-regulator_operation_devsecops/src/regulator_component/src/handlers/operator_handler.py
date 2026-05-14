# handlers/operator_handler.py
import logging
from datetime import datetime

from ..models import OperatorRequest, OperatorResult
from ..certificate_manager import CertificateManager
from ..broker_client import BrokerClient
from ..config import Config

logger = logging.getLogger(__name__)


class OperatorHandler:
    def __init__(self, cert_manager: CertificateManager, broker: BrokerClient):
        self.cert_manager = cert_manager
        self.broker = broker

    async def handle(self, message: dict):
        try:
            req = OperatorRequest(**message)
            logger.info(f"Processing operator request {req.message_id}")

            cert = self.cert_manager.create_certificate(
                subject_type="operator",
                subject_id=req.operator_id,
                security_goals=["OPERATOR-AUTH", "MISSION-APPROVAL"]
            )

            result = OperatorResult(
                timestamp=datetime.utcnow(),
                message_id=req.message_id,
                operator_id=req.operator_id,
                certificate_status="certified",
                certificate_id=cert.certificate_id,
                digital_signature=cert.digital_signature
            )
            await self.broker.publish(Config.TOPIC_OPERATOR_RESULT, result.model_dump_json())
            logger.info(f"Operator {req.operator_id} certified with {cert.certificate_id}")
        except Exception as e:
            logger.error(f"Error processing operator request: {e}", exc_info=True)
