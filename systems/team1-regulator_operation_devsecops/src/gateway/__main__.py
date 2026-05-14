"""Entrypoint for regulator gateway.

NOTE: Требует пакеты broker и sdk из репозитория интегратора.
Запускается только в среде интегратора через Makefile/docker-compose.
"""
import os

# broker — внешняя зависимость из репозитория интегратора
from broker.bus_factory import create_system_bus
from systems.regulator.src.gateway.src.gateway import RegulatorGateway


def main():
    system_id = os.environ.get("SYSTEM_ID", "regulator")
    health_port = int(os.environ.get("HEALTH_PORT", "0")) or None

    bus = create_system_bus(client_id=system_id)
    gateway = RegulatorGateway(
        system_id=system_id,
        bus=bus,
        health_port=health_port,
    )
    gateway.run_forever()


if __name__ == "__main__":
    main()
