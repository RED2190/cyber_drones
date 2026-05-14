"""Топики и actions для PortManager в составе drone_port."""

import os


_NS = os.environ.get("SYSTEM_NAMESPACE", "")
_P = f"{_NS}." if _NS else ""


class ComponentTopics:
    PORT_MANAGER = f"{_P}components.port_manager"
    STATE_STORE = f"{_P}components.state_store"

    @classmethod
    def all(cls) -> list:
        return [
            cls.PORT_MANAGER,
            cls.STATE_STORE,
        ]


class PortManagerActions:
    REQUEST_LANDING = "request_landing"
    FREE_SLOT = "free_slot"
    GET_PORT_STATUS = "get_port_status"
