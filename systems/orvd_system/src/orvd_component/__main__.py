"""Точка входа для orvd_component в составе системы."""
import os
import sys
import signal
import time

from broker.bus_factory import create_system_bus
from systems.orvd_system.src.orvd_component.src.orvd_component import OrvdComponent
from systems.orvd_system.src.orvd_component.topics import ComponentTopics


def main():
    component_id = os.environ.get("COMPONENT_ID", "orvd_component")
    name = os.environ.get("COMPONENT_NAME", component_id.replace("_", " ").title())

    bus = create_system_bus(client_id=component_id)

    component = OrvdComponent(
        component_id=component_id,
        name=name,
        bus=bus,
        topic=ComponentTopics.ORVD_COMPONENT,
    )

    component.start()

    print(f"[{component_id}] Running. Press Ctrl+C to stop.")

    def signal_handler(sig, frame):
        print(f"\n[{component_id}] Received signal {sig}, shutting down...")
        component.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while component._running:
            signal.pause()
    except AttributeError:
        while component._running:
            time.sleep(1)


if __name__ == "__main__":
    main()