from __future__ import annotations

from flask import Blueprint

from demo.webui.runtime import demo
from demo.webui.utils import execute, json_payload, optional_text


nus_api = Blueprint("nus_api", __name__)


@nus_api.post("/api/action/broker-down")
def broker_down():
    return execute("broker-down", demo.broker_down)


@nus_api.post("/api/action/gcs-down")
def gcs_down():
    return execute("gcs-down", demo.gcs_down)


@nus_api.post("/api/action/gcs-interactive-down")
def gcs_interactive_down():
    return execute("gcs-interactive-down", demo.gcs_interactive_down)


@nus_api.get("/api/action/ps")
def ps():
    return execute("ps", demo.gcs_ps)


@nus_api.post("/api/action/landing")
def landing():
    payload = json_payload()

    def run():
        return demo.request_landing(
            drone_id=optional_text(payload.get("drone_id")) or "drone-demo-1",
            model=optional_text(payload.get("model")) or "DemoCopter-X",
        )

    return execute("landing", run)


@nus_api.post("/api/action/charging")
def charging():
    payload = json_payload()

    def run():
        battery = float(payload.get("battery", 30))
        return demo.request_charging(
            drone_id=optional_text(payload.get("drone_id")) or "drone-demo-1",
            battery=battery,
        )

    return execute("charging", run)


@nus_api.post("/api/action/takeoff")
def takeoff():
    payload = json_payload()

    def run():
        return demo.request_takeoff(optional_text(payload.get("drone_id")) or "drone-demo-1")

    return execute("takeoff", run)


@nus_api.post("/api/action/submit-task")
def submit_task():
    payload = json_payload()

    def run():
        waypoints = payload.get("waypoints")
        return demo.submit_task(waypoints=waypoints)

    return execute("submit-task", run)


@nus_api.post("/api/action/assign-task")
def assign_task():
    payload = json_payload()

    def run():
        mission_id = optional_text(payload.get("mission_id"))
        if not mission_id:
            raise ValueError("mission_id is required")
        return demo.assign_task(
            mission_id=mission_id,
            drone_id=optional_text(payload.get("drone_id")) or "drone-demo-1",
        )

    return execute("assign-task", run)


@nus_api.post("/api/action/start-task")
def start_task():
    payload = json_payload()

    def run():
        mission_id = optional_text(payload.get("mission_id"))
        if not mission_id:
            raise ValueError("mission_id is required")
        return demo.start_task(
            mission_id=mission_id,
            drone_id=optional_text(payload.get("drone_id")) or "drone-demo-1",
        )

    return execute("start-task", run)


@nus_api.post("/api/action/mission")
def mission():
    payload = json_payload()

    def run():
        mission_id = optional_text(payload.get("mission_id"))
        if not mission_id:
            raise ValueError("mission_id is required")
        return demo.get_mission(mission_id)

    return execute("mission", run)


@nus_api.post("/api/action/drone-state")
def drone_state():
    payload = json_payload()

    def run():
        drone_id = optional_text(payload.get("drone_id"))
        if not drone_id:
            raise ValueError("drone_id is required")
        return demo.get_drone_state(drone_id)

    return execute("drone-state", run)


@nus_api.post("/api/action/snapshot")
def snapshot():
    payload = json_payload()

    def run():
        return demo.gcs_snapshot(
            drone_id=optional_text(payload.get("drone_id")) or "drone-demo-1",
            mission_id=optional_text(payload.get("mission_id")),
        )

    return execute("snapshot", run)
