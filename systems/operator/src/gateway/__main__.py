"""Точка входа для gateway Operator."""
import os

from broker.bus_factory import create_system_bus
from systems.operator.src.gateway.src.gateway import OperatorGateway


def main() -> None:
    system_id = os.environ.get("SYSTEM_ID", "operator")
    health_port = int(os.environ.get("HEALTH_PORT", "0")) or None

    bus = create_system_bus(client_id=system_id)
    gateway = OperatorGateway(system_id=system_id, bus=bus, health_port=health_port)
    gateway.run_forever()


if __name__ == "__main__":
    main()

