"""Точка входа для SecurityMonitorComponent как отдельного компонента.

Запуск: python -m systems.agrodron.src.security_monitor
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
from systems.agrodron.src.security_monitor import config
from systems.agrodron.src.security_monitor.src.security_monitor import SecurityMonitorComponent


def main() -> None:
    component_id = os.environ.get("COMPONENT_ID", "security_monitor")
    bus = create_system_bus(client_id=component_id)

    component = SecurityMonitorComponent(
        component_id=component_id,
        bus=bus,
        topic=config.component_topic(),
    )
    component.start()

    print(f"[{component_id}] Running SecurityMonitorComponent. Press Ctrl+C to stop.")

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


