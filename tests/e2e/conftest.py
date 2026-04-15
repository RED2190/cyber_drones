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

STARTUP_TIMEOUT = int(os.environ.get("E2E_STARTUP_TIMEOUT", "120"))


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
GCS_GATEWAY_URL = os.environ.get("GCS_GATEWAY_URL", "http://localhost:8091")


@pytest.fixture(scope="session", autouse=True)
def wait_for_services() -> None:
    """Block until all E2E services respond."""
    _wait_for_http(f"{AGREGATOR_URL}/health", "Agregator")
    _wait_for_http(f"{ANALYTICS_URL}/", "DroneAnalytics")
    _wait_for_http(f"{REGULATOR_URL}/health", "Regulator")
    _wait_for_http(f"{GCS_GATEWAY_URL}/health", "GCS gateway")


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
    resp = requests.post(
        f"{ANALYTICS_URL}/auth/login",
        json={"username": ANALYTICS_USER, "password": ANALYTICS_PASSWORD},
        timeout=10,
    )
    assert resp.status_code == 200, f"DroneAnalytics login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="session")
def kafka_bus():
    """Create a Kafka SystemBus for the test host to send bus messages."""
    os.environ.setdefault("BROKER_TYPE", "kafka")
    os.environ.setdefault("KAFKA_BOOTSTRAP_SERVERS", KAFKA_BOOTSTRAP)
    os.environ.setdefault("BROKER_USER", os.environ.get("ADMIN_USER", "admin"))
    os.environ.setdefault("BROKER_PASSWORD", os.environ.get("ADMIN_PASSWORD", "admin_secret_123"))

    from broker.bus_factory import create_system_bus
    bus = create_system_bus(client_id="e2e_test_host")
    bus.start()
    yield bus
    bus.stop()
