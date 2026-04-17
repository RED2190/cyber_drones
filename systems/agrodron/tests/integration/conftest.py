"""Shared fixtures for integration tests."""
import os
import tempfile
import pytest

os.environ.setdefault("TOPIC_VERSION", "v1")
os.environ.setdefault("SYSTEM_NAME", "Test")
os.environ.setdefault("INSTANCE_ID", "Test001")
os.environ.setdefault("SITL_TOPIC", "v1.SITL.SITL001.main")
os.environ.setdefault("ORVD_TOPIC", "v1.ORVD.ORVD001.main")
os.environ.setdefault("NUS_TOPIC", "v1.NUS.NUS001.main")
os.environ.setdefault("DRONEPORT_TOPIC", "v1.Droneport.DP001.main")

from systems.agrodron.tests.integration.integration_bus import IntegrationBus
from systems.agrodron.src.common.topic_utils import topic_for


WPL_SAMPLE = "QGC WPL 110\n0\t1\t0\t16\t0\t0\t0\t0\t60.0\t30.0\t5.0\t1"


@pytest.fixture
def bus():
    return IntegrationBus()


@pytest.fixture
def topic_prefix():
    return "v1.Test.Test001"


@pytest.fixture
def tmp_journal(tmp_path):
    path = str(tmp_path / "journal.ndjson")
    os.environ["JOURNAL_FILE_PATH"] = path
    yield path
