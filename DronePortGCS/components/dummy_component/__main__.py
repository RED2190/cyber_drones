"""
Точка входа: python -m components.dummy_component

Запуск без брокера (standalone).
"""
import os
import sys

from components.dummy_component.src.dummy_component import DummyComponent


def main():
    component_id = os.environ.get("COMPONENT_ID", "dummy_standalone")
    name = os.environ.get("COMPONENT_NAME", component_id.replace("_", " ").title())

    print(f"[{component_id}] Starting in standalone mode (no broker)")
    print(f"[{component_id}] DummyComponent '{name}' ready")
    print(f"[{component_id}] Note: to run with broker, include this component in a system")


if __name__ == "__main__":
    main()
