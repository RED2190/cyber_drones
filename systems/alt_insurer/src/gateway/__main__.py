"""Точка входа для gateway alt_insurer."""
import os

from broker.bus_factory import create_system_bus
from systems.alt_insurer.src.gateway.src.gateway import InsurerGateway


def main():
    system_id = os.environ.get("SYSTEM_ID", "alt_insurer")
    health_port = int(os.environ.get("HEALTH_PORT", "0")) or None
    # Опциональный override системного топика — нужен, когда alt_insurer
    # выступает заменой системы insurer (e2e MQTT): listening_topic =
    # systems.insurer вместо дефолтного systems.alt_insurer.
    topic_override = os.environ.get("INSURER_GATEWAY_TOPIC") or None

    bus = create_system_bus(client_id=system_id)
    gateway = InsurerGateway(
        system_id=system_id,
        bus=bus,
        health_port=health_port,
        topic_override=topic_override,
    )
    gateway.run_forever()


if __name__ == "__main__":
    main()
