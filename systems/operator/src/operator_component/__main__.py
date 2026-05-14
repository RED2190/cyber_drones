"""Точка входа для OperatorComponent."""
import logging
import os
import time

from broker.bus_factory import create_system_bus
from systems.operator.src.operator_component.src.operator_component import OperatorComponent
from systems.operator.src.operator_component.topics import ExternalTopics

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [%(name)s] %(message)s",
)


def main() -> None:
    component_id = os.environ.get("COMPONENT_ID", "operator_component")
    bus = create_system_bus(client_id=component_id)
    component = OperatorComponent(component_id=component_id, bus=bus)
    component.start()

    bus.subscribe(ExternalTopics.AGREGATOR_REQUESTS, component._handle_message)
    print(f"[{component_id}] Subscribed to Agregator requests: "
          f"{ExternalTopics.AGREGATOR_REQUESTS}")

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()

