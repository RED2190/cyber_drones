"""
E2E test fixtures.

The tests expect the full Docker environment to be up.
Ports on localhost:
    - 8080: Agregator REST (Flask)
    - 9092: Kafka
    - 8090: DroneAnalytics backend
"""
from __future__ import annotations

import os
import time
from typing import Generator

import pytest
import requests

AGREGATOR_URL = os.environ.get("AGREGATOR_URL", "http://localhost:8081")
ANALYTICS_URL = os.environ.get("ANALYTICS_URL", "http://localhost:8090")
ANALYTICS_API_KEY = os.environ.get("ANALYTICS_API_KEY", "test-api-key-e2e-12345")
ANALYTICS_USER = os.environ.get("ANALYTICS_USER", "admin")
ANALYTICS_PASSWORD = os.environ.get("ANALYTICS_PASSWORD", "admin1234")

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))

STARTUP_TIMEOUT = int(os.environ.get("E2E_STARTUP_TIMEOUT", "180"))
SKIP_ANALYTICS = os.environ.get("E2E_SKIP_ANALYTICS", "0") not in ("0", "", "false", "False")


def _warmup_orvd_component(bus) -> None:
    """Drain OrvdComponent's Kafka consumer backlog before tests begin.

    The OrvdComponent processes messages sequentially.  On a fresh-start with
    auto_offset_reset='earliest' there may be messages already queued on
    'components.orvd_component' from a previous (uncommitted) run.  We ping
    OrvdComponent directly (bypassing the gateway) until it responds, which
    confirms the backlog is cleared and the component is ready to handle
    test requests within normal timeouts.
    """
    deadline = time.time() + 60
    while time.time() < deadline:
        resp = bus.request(
            "components.orvd_component",
            {"action": "ping", "sender": "e2e_warmup", "payload": {}},
            timeout=10,
        )
        if resp is not None and (resp.get("payload") or {}).get("pong"):
            return
        time.sleep(3)
    # Non-fatal: ORVD may not be running; tests will skip/handle accordingly.


def _wait_for_http(url: str, label: str, timeout: int = STARTUP_TIMEOUT) -> None:
    deadline = time.time() + timeout
    last_err = ""
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=3)
            if r.status_code < 500:
                return
            last_err = f"HTTP {r.status_code}"
        except requests.ConnectionError as exc:
            last_err = str(exc)
        except requests.Timeout:
            last_err = "timeout"
        time.sleep(2)
    pytest.fail(f"{label} not reachable at {url} after {timeout}s: {last_err}")


REGULATOR_URL = os.environ.get("REGULATOR_URL", "http://localhost:8088")


@pytest.fixture(scope="session", autouse=True)
def wait_for_services() -> None:
    """Block until all E2E services respond."""
    _wait_for_http(f"{AGREGATOR_URL}/health", "Agregator")
    _wait_for_http(f"{REGULATOR_URL}/health", "Regulator")
    if not SKIP_ANALYTICS:
        _wait_for_http(f"{ANALYTICS_URL}/", "DroneAnalytics")


@pytest.fixture(scope="session")
def agregator_url() -> str:
    return AGREGATOR_URL


@pytest.fixture(scope="session")
def analytics_url() -> str:
    return ANALYTICS_URL


@pytest.fixture(scope="session")
def analytics_api_key() -> str:
    return ANALYTICS_API_KEY


@pytest.fixture(scope="session")
def analytics_bearer_token() -> str:
    """Log in to DroneAnalytics and return an access token."""
    if SKIP_ANALYTICS:
        pytest.skip("Analytics disabled (E2E_SKIP_ANALYTICS=1)")
    resp = requests.post(
        f"{ANALYTICS_URL}/auth/login",
        json={"username": ANALYTICS_USER, "password": ANALYTICS_PASSWORD},
        timeout=10,
    )
    assert resp.status_code == 200, f"DroneAnalytics login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="session")
def kafka_bus():
    """SystemBus для сценария e2e: Kafka или MQTT по BROKER_TYPE (совпадает с контейнерами).

    Имя фикстуры историческое: при ``make e2e-mqtt-test`` задаётся ``BROKER_TYPE=mqtt``.
    """
    bt = os.environ.get("BROKER_TYPE", "kafka").strip().lower()
    os.environ.setdefault("BROKER_USER", os.environ.get("ADMIN_USER", "admin"))
    os.environ.setdefault("BROKER_PASSWORD", os.environ.get("ADMIN_PASSWORD", "admin_secret_123"))
    if bt == "mqtt":
        os.environ["BROKER_TYPE"] = "mqtt"
        os.environ.setdefault("MQTT_BROKER", MQTT_BROKER)
        os.environ.setdefault("MQTT_PORT", str(MQTT_PORT))
    else:
        os.environ.setdefault("BROKER_TYPE", "kafka")
        os.environ.setdefault("KAFKA_BOOTSTRAP_SERVERS", KAFKA_BOOTSTRAP)

    from broker.bus_factory import create_system_bus
    bus = create_system_bus(client_id="e2e_test_host")
    bus.start()
    _warmup_orvd_component(bus)
    yield bus
    bus.stop()


@pytest.fixture(scope="session")
def mqtt_bus():
    """Create an MQTT SystemBus for the test host to send bus messages.

    Uses the same single-broker SystemBus API as kafka_bus — request/publish.
    Requires mosquitto on localhost:1883 (docker profile=mqtt) and systems
    running with BROKER_TYPE=mqtt.
    """
    os.environ.setdefault("MQTT_BROKER", MQTT_BROKER)
    os.environ.setdefault("MQTT_PORT", str(MQTT_PORT))
    os.environ.setdefault("BROKER_USER", os.environ.get("ADMIN_USER", "admin"))
    os.environ.setdefault("BROKER_PASSWORD", os.environ.get("ADMIN_PASSWORD", "admin_secret_123"))

    from broker.bus_factory import create_system_bus
    bus = create_system_bus(
        bus_type="mqtt",
        client_id="e2e_test_host",
    )
    bus.start()
    yield bus
    bus.stop()
