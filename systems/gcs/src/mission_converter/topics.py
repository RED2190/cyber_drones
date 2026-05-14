"""Топики и actions для MissionConverterComponent."""

import os


_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class ComponentTopics:
    MISSION_CONVERTER = f"{_P}components.mission_converter"
    MISSION_STORE = f"{_P}components.mission_store"

    @classmethod
    def all(cls) -> list:
        return [
            cls.MISSION_CONVERTER,
            cls.MISSION_STORE,
        ]


class MissionActions:
    MISSION_PREPARE = "mission.prepare"
