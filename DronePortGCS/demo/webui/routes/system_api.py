from __future__ import annotations

from flask import Blueprint, jsonify

from demo.interactive_demo import default_task_waypoints
from demo.webui.runtime import JOBS, JOB_LOCK, STREAMING_ACTIONS, demo
from demo.webui.utils import job_payload, json_payload, optional_text, start_job


system_api = Blueprint("system_api", __name__)


@system_api.get("/api/health")
def health():
    return jsonify({"ok": True})


@system_api.get("/api/config")
def config():
    return jsonify(
        {
            "default_waypoints": default_task_waypoints(),
            "client_id": demo.client_id,
        }
    )


@system_api.post("/api/jobs/<action_name>")
def start_job_route(action_name: str):
    if action_name not in STREAMING_ACTIONS:
        return jsonify({"ok": False, "error": f"streaming action is not supported: {action_name}"}), 404
    payload = json_payload()
    label = optional_text(payload.get("label")) or action_name
    return start_job(action_name, label)


@system_api.get("/api/jobs/<job_id>")
def get_job(job_id: str):
    with JOB_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return jsonify({"ok": False, "error": f"job not found: {job_id}"}), 404
        return jsonify(job_payload(job))


@system_api.post("/api/action/logs")
def logs():
    payload = json_payload()

    def run():
        stack = payload.get("stack", "broker")
        service = optional_text(payload.get("service"))
        tail = int(payload.get("tail", 100))
        if stack not in {"broker", "gcs", "drone_port", "cyber_drons"}:
            raise ValueError("stack must be one of: broker, gcs, drone_port, cyber_drons")
        return demo.logs(stack=stack, service=service, tail=tail)

    from demo.webui.utils import execute

    return execute("logs", run)
