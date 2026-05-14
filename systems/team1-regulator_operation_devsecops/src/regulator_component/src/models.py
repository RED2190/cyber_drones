from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


class FirmwareRequest(BaseModel):
    request_id: str
    timestamp: datetime
    developer_id: str
    firmware: Dict[str, Any]   # repository_url, commit_hash, version
    drone_type: str


class FirmwareResult(BaseModel):
    request_id: str
    timestamp: datetime
    status: str   # "CERTIFIED" or "REJECTED"
    certificate: Optional[Dict[str, Any]] = None


class DroneRequest(BaseModel):
    request_id: str
    timestamp: datetime
    drone: Dict[str, Any]   # model, serial_number, manufacturer
    firmware: Dict[str, Any]   # version, certificate_id


class DroneResult(BaseModel):
    request_id: str
    timestamp: datetime
    status: str   # "APPROVED" or "REJECTED"
    drone: Optional[Dict[str, Any]] = None
    certificate: Optional[Dict[str, Any]] = None


class OperatorRequest(BaseModel):
    timestamp: datetime
    message_id: str
    operator_id: str
    drone_id: str
    digital_signature: str


class OperatorResult(BaseModel):
    timestamp: datetime
    message_id: str
    operator_id: str
    certificate_status: str   # "certified" or "rejected"
    certificate_id: Optional[str] = None
    digital_signature: str


class InsurerRequest(BaseModel):
    timestamp: datetime
    message_id: str
    insurer_id: str
    requirements_checked: Optional[List[str]] = None
    status: Optional[str] = None
    digital_signature: Optional[str] = None
    # дополнительные поля от UI
    order_id: Optional[str] = None
    amount: Optional[float] = None
    incident_id: Optional[str] = None


class InsurerResponse(BaseModel):
    timestamp: datetime
    message_id: str
    insurer_id: str
    approved: bool
    reason: Optional[str] = None
    digital_signature: str


class Certificate(BaseModel):
    certificate_id: str
    issued_at: datetime
    valid_until: datetime
    subject_type: str   # "firmware", "drone", "operator"
    subject_id: str
    security_goals: List[str]
    digital_signature: str

    def is_valid(self) -> bool:
        return datetime.utcnow() < self.valid_until