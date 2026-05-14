"""Точка входа для gateway DronePort."""

import os

from broker.src.bus_factory import create_system_bus
from .src.gateway import DronePortGateway


def main() -> None:
    system_id = os.environ.get("SYSTEM_ID", "drone_port")
    health_port = int(os.environ.get("HEALTH_PORT", "0")) or None

    bus = create_system_bus(client_id=system_id)
    gateway = DronePortGateway(
        system_id=system_id,
        bus=bus,
        health_port=health_port,
    )
    gateway.run_forever()


if __name__ == "__main__":
    main()
