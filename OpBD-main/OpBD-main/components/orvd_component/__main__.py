"""
Точка входа: python -m components.orvd_component

Запуск без брокера (standalone).
"""
import os
import sys

from components.orvd_component.src.orvd_component import OrvdComponent


def main():
    component_id = os.environ.get("COMPONENT_ID", "orvd_standalone")
    name = os.environ.get("COMPONENT_NAME", component_id.replace("_", " ").title())

    print(f"[{component_id}] Starting orvd component in standalone mode (no broker)")
    print(f"[{component_id}] OrvdComponent '{name}' ready")
    print(f"[{component_id}] Note: to run with broker, include this component in a system")


if __name__ == "__main__":
    main()
