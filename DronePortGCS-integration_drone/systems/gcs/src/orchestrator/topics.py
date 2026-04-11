"""Топики, actions и events для OrchestratorComponent."""

from functools import partial

from sdk.topic_naming import build_component_topic as _build_component_topic


build_component_topic = partial(
    _build_component_topic,
    system_env_var="GCS_SYSTEM_NAME",
    default_system_name="gcs",
)


class ComponentTopics:
    GCS_ORCHESTRATOR = build_component_topic("orchestrator")
    GCS_PATH_PLANNER = build_component_topic("path_planner")
    GCS_MISSION_CONVERTER = build_component_topic("mission_converter")
    GCS_DRONE_MANAGER = build_component_topic("drone_manager")
    GCS_DRONE_STORE = build_component_topic("drone_store")
    GCS_MISSION_STORE = build_component_topic("mission_store")

    @classmethod
    def all(cls) -> list:
        return [
            cls.GCS_ORCHESTRATOR,
            cls.GCS_PATH_PLANNER,
            cls.GCS_MISSION_CONVERTER,
            cls.GCS_DRONE_MANAGER,
            cls.GCS_DRONE_STORE,
            cls.GCS_MISSION_STORE,
        ]


class OrchestratorActions:
    TASK_SUBMIT = "task.submit"
    TASK_ASSIGN = "task.assign"
    TASK_START = "task.start"
