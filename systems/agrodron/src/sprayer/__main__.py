"""Точка входа для SprayerComponent в составе системы.

Запуск: python -m systems.agrodron.src.sprayer
"""
import os
import signal
import sys

from broker.bus_factory import create_system_bus
from systems.agrodron.src.sprayer import config
from systems.agrodron.src.sprayer.src.sprayer import SprayerComponent


def main() -> None:
    component_id = os.environ.get("COMPONENT_ID", "sprayer")
    bus = create_system_bus(client_id=component_id)
    component = SprayerComponent(
        component_id=component_id,
        bus=bus,
        topic=config.component_topic(),
    )
    component.start()
    print(f"[{component_id}] Running SprayerComponent. Press Ctrl+C to stop.")

    def signal_handler(sig, frame):
        print(f"\n[{component_id}] Received signal {sig}, shutting down...")
        component.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.pause()


if __name__ == "__main__":
    main()

