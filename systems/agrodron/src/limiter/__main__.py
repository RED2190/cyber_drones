"""Точка входа для LimiterComponent в составе системы.

Запуск: python -m systems.agrodron.src.limiter
"""
import os
import signal
import sys
import time

from broker.bus_factory import create_system_bus
from systems.agrodron.src.limiter import config
from systems.agrodron.src.limiter.src.limiter import LimiterComponent


def main() -> None:
    component_id = os.environ.get("COMPONENT_ID", "limiter")
    bus = create_system_bus(client_id=component_id)

    component = LimiterComponent(
        component_id=component_id,
        bus=bus,
        topic=config.component_topic(),
    )
    component.start()

    print(f"[{component_id}] Running LimiterComponent. Press Ctrl+C to stop.")

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


