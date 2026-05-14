"""Точка входа для MotorsComponent в составе системы.

Запуск: python -m systems.agrodron.src.motors
"""
import logging
import os
import signal
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [%(name)s] %(message)s",
)

from broker.bus_factory import create_system_bus
from systems.agrodron.src.motors import config
from systems.agrodron.src.motors.src.motors import MotorsComponent


def main() -> None:
    component_id = os.environ.get("COMPONENT_ID", "motors")
    bus = create_system_bus(client_id=component_id)
    component = MotorsComponent(
        component_id=component_id,
        bus=bus,
        topic=config.component_topic(),
    )
    component.start()
    print(f"[{component_id}] Running MotorsComponent. Press Ctrl+C to stop.")

    def signal_handler(sig, frame):
        print(f"\n[{component_id}] Received signal {sig}, shutting down...")
        component.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.pause()


if __name__ == "__main__":
    main()

