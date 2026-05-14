"""Точка входа для aggregator в составе dummy_fabric."""
import os, sys, signal, time

from broker.bus_factory import create_system_bus
from systems.dummy_fabric.src.aggregator.src.component import AggregatorComponent
from systems.dummy_fabric.src.aggregator.topics import ComponentTopics


def main():
    cid = os.environ.get("COMPONENT_ID", "fabric_aggregator")
    bus = create_system_bus(client_id=cid)
    comp = AggregatorComponent(
        component_id=cid, component_type="aggregator",
        topic=ComponentTopics.AGGREGATOR, bus=bus,
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
