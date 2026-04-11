import os
import signal
import time

from broker.src.bus_factory import create_system_bus
from systems.gcs.src.path_planner.src.path_planner import PathPlannerComponent


def main():
    component_id = os.environ.get("COMPONENT_ID", "gcs_path_planner")

    bus = create_system_bus(client_id=component_id)
    component = PathPlannerComponent(component_id=component_id, bus=bus)

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
