"""Точка входа для insurance_service в составе alt_insurer."""
import os
import sys
import signal
import time

from broker.bus_factory import create_system_bus
from systems.alt_insurer.src.insurance_service.src.insurance_service import InsuranceService
from systems.alt_insurer.src.insurance_service.topics import ComponentTopics


def main():
    component_id = os.environ.get("COMPONENT_ID", "insurer_service")

    bus = create_system_bus(client_id=component_id)
    service = InsuranceService(
        component_id=component_id,
        bus=bus,
        topic=ComponentTopics.INSURANCE_SERVICE,
    )
    service.start()

    print(f"[{component_id}] Running. Press Ctrl+C to stop.")

    def signal_handler(sig, frame):
        print(f"\n[{component_id}] Received signal {sig}, shutting down...")
        service.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while service._running:
            signal.pause()
    except AttributeError:
        while service._running:
            time.sleep(1)


if __name__ == "__main__":
    main()
