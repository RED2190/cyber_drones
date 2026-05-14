import asyncio
import os
from pathlib import Path

from .src.config import Config
from .src.logger import setup_logging
from .src.broker_factory import create_broker_adapter
from .src.certificate_manager import CertificateManager
from .src.security_test_runner import SecurityTestRunner
from .src.coverage_controller import CoverageController
from .src.dispatcher import Dispatcher

from .src.handlers.firmware_handler import FirmwareHandler
from .src.handlers.drone_handler import DroneHandler
from .src.handlers.operator_handler import OperatorHandler
from .src.handlers.insurer_handler import InsurerHandler
from .src.handlers.certificate_verify_handler import CertificateVerifyHandler
from .src.handlers.certificate_revoke_handler import CertificateRevokeHandler


async def main():
    logger = setup_logging()
    logger.info("Starting Regulator System (Component Mode)...")

    current_dir = Path(__file__).parent
    default_key_path = current_dir / "src" / "keys" / "regulator_private.pem"
    private_key = os.getenv("PRIVATE_KEY", str(default_key_path))

    cert_manager = CertificateManager(
        cert_storage_path=Config.CERT_STORAGE_PATH,
        crl_storage_path=Config.CRL_STORAGE_PATH,
        private_key=private_key
    )

    test_runner = SecurityTestRunner(mock=Config.MOCK_SECURITY_TESTS)
    coverage_controller = CoverageController(mock=Config.MOCK_COVERAGE)

    broker = create_broker_adapter()

    firmware_handler = FirmwareHandler(cert_manager, test_runner, coverage_controller, broker)
    drone_handler = DroneHandler(cert_manager, broker)
    operator_handler = OperatorHandler(cert_manager, broker)
    insurer_handler = InsurerHandler(broker)
    verify_handler = CertificateVerifyHandler(cert_manager, broker)
    revoke_handler = CertificateRevokeHandler(cert_manager, broker)

    dispatcher = Dispatcher()

    routes = {
        Config.TOPIC_FIRMWARE_REQUEST:    firmware_handler.handle,
        Config.TOPIC_DRONE_REQUEST:       drone_handler.handle,
        Config.TOPIC_OPERATOR_REQUEST:    operator_handler.handle,
        Config.TOPIC_INSURER_REQUEST:     insurer_handler.handle,
        Config.TOPIC_CERT_VERIFY_REQUEST: verify_handler.handle,
        Config.TOPIC_CERT_REVOKE_REQUEST: revoke_handler.handle,
    }

    for topic, handler_func in routes.items():
        dispatcher.register(topic, handler_func)
        logger.info(f"Registered route: {topic}")

    async def safe_dispatch(topic, data):
        await dispatcher.dispatch(topic, data)

    try:
        logger.info("Connecting to broker...")
        await broker.connect()

        for topic in dispatcher.routes.keys():
            await broker.subscribe(topic, safe_dispatch)
            logger.info(f"Subscribed to topic: {topic}")

        logger.info("Regulator Component is ready and consuming messages.")
        await broker.start_consuming()

        while True:
            await asyncio.sleep(1)

    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutdown initiated...")
    except Exception as e:
        logger.error(f"Critical system error: {e}")
    finally:
        logger.info("Closing connections...")
        await broker.close()
        logger.info("Regulator stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
