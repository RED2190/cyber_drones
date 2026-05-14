"""Generic entrypoint for AnalyticsJournalComponent.

All config comes from environment variables:
    COMPONENT_ID, JOURNAL_TOPIC (=listen topic), ANALYTICS_URL, ANALYTICS_API_KEY,
    ANALYTICS_SERVICE_NAME, ANALYTICS_SERVICE_ID, BROKER_TYPE, etc.
"""
import os
import signal
import sys
import time

from broker.bus_factory import create_system_bus
from sdk.analytics_journal import AnalyticsJournalComponent


def main() -> None:
    component_id = os.environ.get("COMPONENT_ID", "journal")
    topic = os.environ.get("JOURNAL_TOPIC", f"components.{component_id}")

    bus = create_system_bus(client_id=component_id)
    component = AnalyticsJournalComponent(
        component_id=component_id,
        bus=bus,
        topic=topic,
    )
    component.start()

    print(f"[{component_id}] Journal running. Ctrl+C to stop.")

    def on_signal(sig, frame):
        print(f"\n[{component_id}] Received signal {sig}, shutting down...")
        component.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    try:
        while component._running:
            signal.pause()
    except AttributeError:
        while component._running:
            time.sleep(1)


if __name__ == "__main__":
    main()
