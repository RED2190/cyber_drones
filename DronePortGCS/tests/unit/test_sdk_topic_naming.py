import os

from sdk.topic_naming import build_component_topic, clean_topic_part, instance_id, system_name, topic_version


def test_clean_topic_part_normalizes_slashes():
    assert clean_topic_part(" v1/gcs/1 ") == "v1.gcs.1"


def test_build_component_topic_uses_custom_system_env(monkeypatch):
    monkeypatch.setenv("TOPIC_VERSION", "v2")
    monkeypatch.setenv("GCS_SYSTEM_NAME", "control")
    monkeypatch.setenv("INSTANCE_ID", "42")

    assert build_component_topic(
        "orchestrator",
        system_env_var="GCS_SYSTEM_NAME",
        default_system_name="gcs",
    ) == "v2.control.42.orchestrator"


def test_build_component_topic_falls_back_to_defaults(monkeypatch):
    monkeypatch.delenv("TOPIC_VERSION", raising=False)
    monkeypatch.delenv("SYSTEM_NAME", raising=False)
    monkeypatch.delenv("INSTANCE_ID", raising=False)

    assert build_component_topic(
        "drone_manager",
        system_env_var="SYSTEM_NAME",
        default_system_name="drone_port",
    ) == "v1.drone_port.1.drone_manager"


def test_topic_helpers_return_defaults_when_env_empty(monkeypatch):
    monkeypatch.setenv("TOPIC_VERSION", "")
    monkeypatch.setenv("INSTANCE_ID", "")
    monkeypatch.setenv("SYSTEM_NAME", "")

    assert topic_version() == "v1"
    assert instance_id() == "1"
    assert system_name("SYSTEM_NAME", "drone_port") == "drone_port"
