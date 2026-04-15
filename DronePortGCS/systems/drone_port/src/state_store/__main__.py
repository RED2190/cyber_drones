"""Точка входа для StateStore."""
import logging
import os
import signal
import time

from broker.src.bus_factory import create_system_bus
from systems.drone_port.src.state_store.src.state_store import StateStore


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    component_id = os.environ.get("COMPONENT_ID", "state_store")
    redis_host = os.environ.get("REDIS_HOST", "redis")
    redis_port = int(os.environ.get("REDIS_PORT", "6379"))
    bus = create_system_bus(client_id=component_id)
    component = StateStore(
        component_id=component_id,
        name=component_id,
        bus=bus,
        redis_host=redis_host,
        redis_port=redis_port,
    )

    def _shutdown(sig, frame):
        print(f"\n[{component_id}] Received signal {sig}, shutting down...")
        component.stop()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    component.start()
    print(f"[{component_id}] Running. Press Ctrl+C to stop.")

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
