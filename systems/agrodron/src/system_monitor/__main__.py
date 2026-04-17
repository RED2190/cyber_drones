"""Точка входа: python -m systems.agrodron.src.system_monitor"""
import os
import signal
import sys

from broker.bus_factory import create_system_bus
from systems.agrodron.src.system_monitor import config
from systems.agrodron.src.system_monitor.src.system_monitor import SystemMonitorComponent


def main() -> None:
    component_id = os.environ.get("COMPONENT_ID", "system_monitor")
    bus = create_system_bus(client_id=component_id)
    component = SystemMonitorComponent(
        component_id=component_id,
        bus=bus,
        topic=config.component_topic(),
    )
    component.start()
    print(f"[{component_id}] Running SystemMonitorComponent. Press Ctrl+C to stop.")

    def signal_handler(sig, frame):
        print(f"\n[{component_id}] Received signal {sig}, shutting down...")
        component.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        signal.pause()
    except AttributeError:
        import time
        while component._running:
            time.sleep(1)


if __name__ == "__main__":
    main()
