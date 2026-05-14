"""Entrypoint for regulator component."""
import os
import signal
import sys
import time

from broker.bus_factory import create_system_bus
from systems.regulator.src.regulator_component.src.regulator_component import RegulatorComponent
from systems.regulator.src.regulator_component.topics import ComponentTopics


def main():
    component_id = os.environ.get("COMPONENT_ID", "regulator_component")

    bus = create_system_bus(client_id=component_id)
    component = RegulatorComponent(
        component_id=component_id,
        bus=bus,
        topic=ComponentTopics.REGULATOR_COMPONENT,
    )
    component.start()

    print(f"[{component_id}] Running.")

    def signal_handler(sig, frame):
        print(f"\n[{component_id}] Shutting down...")
        component.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    while component._running:
        time.sleep(1)


if __name__ == "__main__":
    main()
