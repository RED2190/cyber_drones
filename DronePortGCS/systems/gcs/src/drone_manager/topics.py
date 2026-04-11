"""Топики, actions и events для DroneManagerComponent."""

from functools import partial

from sdk.topic_naming import build_component_topic as _build_component_topic


build_component_topic = partial(
    _build_component_topic,
    system_env_var="GCS_SYSTEM_NAME",
    default_system_name="gcs",
)


class ComponentTopics:
    GCS_DRONE = build_component_topic("drone_manager")
    GCS_MISSION_STORE = build_component_topic("mission_store")
    GCS_DRONE_STORE = build_component_topic("drone_store")

    @classmethod
    def all(cls) -> list:
        return [
            cls.GCS_DRONE,
            cls.GCS_MISSION_STORE,
            cls.GCS_DRONE_STORE,
        ]


class DroneManagerActions:
    MISSION_UPLOAD = "mission.upload"
    MISSION_START = "mission.start"
