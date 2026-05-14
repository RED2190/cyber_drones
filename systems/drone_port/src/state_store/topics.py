"""Топики и actions для StateStore в составе drone_port."""

import os


_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class ComponentTopics:
    STATE_STORE = f"{_P}components.state_store"

    @classmethod
    def all(cls) -> list:
        return [
            cls.STATE_STORE,
        ]


class StateStoreActions:
    GET_ALL_PORTS = "get_all_ports"
    UPDATE_PORT = "update_port"
