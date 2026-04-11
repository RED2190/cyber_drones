"""Topics and actions for DroneStoreComponent."""

from functools import partial

from sdk.topic_naming import build_component_topic as _build_component_topic


build_component_topic = partial(
    _build_component_topic,
    system_env_var="GCS_SYSTEM_NAME",
    default_system_name="gcs",
)


class ComponentTopics:
    GCS_DRONE_STORE = build_component_topic("drone_store")

    @classmethod
    def all(cls) -> list:
        return [
            cls.GCS_DRONE_STORE,
        ]


class DroneStoreActions:
    GET_DRONE = "store.get_drone"
    UPDATE_DRONE = "store.update_drone"
    SAVE_TELEMETRY = "telemetry.save"
