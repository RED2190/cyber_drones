"""Топики и actions для MissionConverterComponent."""

from functools import partial

from sdk.topic_naming import build_component_topic as _build_component_topic


build_component_topic = partial(
    _build_component_topic,
    system_env_var="GCS_SYSTEM_NAME",
    default_system_name="gcs",
)


class ComponentTopics:
    GCS_MISSION_CONVERTER = build_component_topic("mission_converter")
    GCS_MISSION_STORE = build_component_topic("mission_store")

    @classmethod
    def all(cls) -> list:
        return [
            cls.GCS_MISSION_CONVERTER,
            cls.GCS_MISSION_STORE,
        ]


class MissionActions:
    MISSION_PREPARE = "mission.prepare"
