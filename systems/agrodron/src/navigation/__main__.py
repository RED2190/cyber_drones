"""Точка входа для NavigationComponent в составе системы.

Запуск: python -m systems.agrodron.src.navigation
"""
import os
import signal
import sys
import time

from broker.bus_factory import create_system_bus
from systems.agrodron.src.navigation import config
from systems.agrodron.src.navigation.src.navigation import NavigationComponent


def main() -> None:
    component_id = os.environ.get("COMPONENT_ID", "navigation")
    bus = create_system_bus(client_id=component_id)

    component = NavigationComponent(
        component_id=component_id,
        bus=bus,
        topic=config.component_topic(),
    )
    component.start()

    print(f"[{component_id}] Running NavigationComponent. Press Ctrl+C to stop.")

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

