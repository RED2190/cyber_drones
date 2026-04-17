"""Entry point for Agrodron system gateway."""

import os

from broker.bus_factory import create_system_bus
from systems.agrodron.src.gateway.src.gateway import AgrodronGateway


def main():
    system_id = os.environ.get("SYSTEM_ID", "agrodron")
    health_port = int(os.environ.get("HEALTH_PORT", "0")) or None

    bus = create_system_bus(client_id=f"{system_id}_gateway")
    gateway = AgrodronGateway(system_id=system_id, bus=bus, health_port=health_port)
    gateway.run_forever()


if __name__ == "__main__":
    main()
