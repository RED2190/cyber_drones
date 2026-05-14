"""Точка входа для orvd в составе dummy_fabric."""
import os, sys, signal, time

from broker.bus_factory import create_system_bus
from systems.dummy_fabric.src.orvd.src.component import OrvdComponent
from systems.dummy_fabric.src.orvd.topics import ComponentTopics


def main():
    cid = os.environ.get("COMPONENT_ID", "fabric_orvd")
    bus = create_system_bus(client_id=cid)
    comp = OrvdComponent(
        component_id=cid, component_type="orvd",
        topic=ComponentTopics.ORVD, bus=bus,
    )
    comp.start()
    print(f"[{cid}] Running. Press Ctrl+C to stop.")

    def stop(sig, frame):
        print(f"\n[{cid}] Shutting down...")
        comp.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        while comp._running:
            signal.pause()
    except AttributeError:
        while comp._running:
            time.sleep(1)


if __name__ == "__main__":
    main()
