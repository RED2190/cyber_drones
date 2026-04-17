"""Точка входа для MissionHandlerComponent в составе системы.

Запуск: python -m systems.agrodron.src.mission_handler
"""
import logging
import os
import signal
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [%(name)s] %(message)s",
)

from broker.bus_factory import create_system_bus
from systems.agrodron.src.mission_handler import config
from systems.agrodron.src.mission_handler.src.mission_handler import MissionHandlerComponent


def main() -> None:
    component_id = os.environ.get("COMPONENT_ID", "mission_handler")
    bus = create_system_bus(client_id=component_id)

    component = MissionHandlerComponent(
        component_id=component_id,
        bus=bus,
        topic=config.component_topic(),
    )
    component.start()

    print(f"[{component_id}] Running MissionHandlerComponent. Press Ctrl+C to stop.")

    def signal_handler(sig, frame):
        print(f"\n[{component_id}] Received signal {sig}, shutting down...")
        component.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while component._running:  # type: ignore[attr-defined]
            signal.pause()
    except AttributeError:
        while component._running:  # type: ignore[attr-defined]
            time.sleep(1)


if __name__ == "__main__":
    main()

