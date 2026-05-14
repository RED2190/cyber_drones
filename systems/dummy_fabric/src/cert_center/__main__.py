"""Точка входа для cert_center в составе dummy_fabric."""
import os, sys, signal, time

from broker.bus_factory import create_system_bus
from systems.dummy_fabric.src.cert_center.src.component import CertCenterComponent
from systems.dummy_fabric.src.cert_center.topics import ComponentTopics


def main():
    cid = os.environ.get("COMPONENT_ID", "fabric_cert_center")
    bus = create_system_bus(client_id=cid)
    comp = CertCenterComponent(
        component_id=cid, component_type="cert_center",
        topic=ComponentTopics.CERT_CENTER, bus=bus,
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
