# handlers/insurer_handler.py
import logging
from datetime import datetime

from ..models import InsurerRequest, InsurerResponse
from ..broker_client import BrokerClient
from ..config import Config

logger = logging.getLogger(__name__)


class InsurerHandler:
    def __init__(self, broker: BrokerClient):
        self.broker = broker

    async def handle(self, message: dict):
        try:
            req = InsurerRequest(**message)
            logger.info(f"Processing insurance claim {req.message_id}")

            approved = True
            reason = None

            response = InsurerResponse(
                timestamp=datetime.utcnow(),
                message_id=req.message_id,
                insurer_id=req.insurer_id,
                approved=approved,
                reason=reason,
                digital_signature="regulator_signature_placeholder"
            )
            await self.broker.publish(Config.TOPIC_INSURER_RESPONSE, response.model_dump_json())
            logger.info(f"Insurance claim {req.message_id} approved")
        except Exception as e:
            logger.error(f"Error processing insurance claim: {e}", exc_info=True)
