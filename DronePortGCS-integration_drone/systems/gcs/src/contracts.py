"""Контракты доменной модели для GCS."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class MissionStatus:
    CREATED: str = "created"
    ASSIGNED: str = "assigned"
    RUNNING: str = "running"

@dataclass(frozen=True)
class DroneStatus:
    AVAILABLE: str = "available"
    RESERVED: str = "reserved"
    BUSY: str = "busy"
