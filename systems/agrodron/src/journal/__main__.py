"""Точка входа для JournalComponent в составе системы.

Запуск: python -m systems.agrodron.src.journal
"""
import os
import signal
import sys
import time

from broker.bus_factory import create_system_bus
from systems.agrodron.src.journal import config
from systems.agrodron.src.journal.src.journal import JournalComponent


def main() -> None:
    component_id = os.environ.get("COMPONENT_ID", "journal")
    bus = create_system_bus(client_id=component_id)

    component = JournalComponent(
        component_id=component_id,
        bus=bus,
        topic=config.component_topic(),
    )
    component.start()

    print(f"[{component_id}] Running JournalComponent. Press Ctrl+C to stop.")

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

