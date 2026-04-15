from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from flask import jsonify, request

from demo.webui.runtime import JOBS, JOB_LOCK, STREAMING_ACTIONS, JobState


def env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() not in {"0", "false", "no"}


def discover_bind_urls(host: str, port: int) -> list[str]:
    urls: list[str] = []
    if host in {"127.0.0.1", "localhost"}:
        return [f"http://{host}:{port}"]

    urls.append(f"http://localhost:{port}")
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("127."):
                continue
            url = f"http://{ip}:{port}"
            if url not in urls:
                urls.append(url)
    except OSError:
        pass
    return urls


def json_payload() -> dict[str, Any]:
    return request.get_json(silent=True) or {}


def optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def serialize(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


def error_payload(action_name: str, exc: Exception) -> dict[str, Any]:
    if isinstance(exc, subprocess.CalledProcessError):
        stdout = (exc.stdout or "").strip()
        stderr = (exc.stderr or "").strip()
        details = []
        if stdout:
            details.append(f"[stdout]\n{stdout}")
        if stderr:
            details.append(f"[stderr]\n{stderr}")
        message = "\n\n".join(details) or str(exc)
    else:
        message = str(exc)
    return {
        "ok": False,
        "action": action_name,
        "error": message,
        "traceback": traceback.format_exc(),
    }


def execute(action_name: str, func: Callable[[], Any]):
    try:
        result = func()
        return jsonify({"ok": True, "action": action_name, "result": result, "result_text": serialize(result)})
    except Exception as exc:  # pragma: no cover - defensive boundary for UI
        print(f"[ERROR] {action_name}: {traceback.format_exc()}")
        return jsonify(error_payload(action_name, exc)), 500


def append_job_log(job_id: str, chunk: str) -> None:
    with JOB_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return
        job.log_text += chunk


def job_payload(job: JobState) -> dict[str, Any]:
    return {
        "ok": job.status == "succeeded",
        "job_id": job.job_id,
        "action": job.action,
        "label": job.label,
        "status": job.status,
        "log_text": job.log_text,
        "result": job.result,
        "result_text": job.result_text,
        "error": job.error,
        "traceback": job.traceback,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
    }


def run_job(job_id: str, action_name: str, label: str, runner: Callable[[Callable[[str], None]], Any]) -> None:
    def on_output(chunk: str) -> None:
        append_job_log(job_id, chunk)

    try:
        result = runner(on_output)
        with JOB_LOCK:
            job = JOBS[job_id]
            job.status = "succeeded"
            job.result = result
            job.result_text = serialize(result)
            if job.result_text and job.result_text not in job.log_text:
                if job.log_text and not job.log_text.endswith("\n"):
                    job.log_text += "\n"
                job.log_text += f"\n[result]\n{job.result_text}\n"
            job.finished_at = datetime.now(timezone.utc).isoformat()
    except Exception as exc:  # pragma: no cover - background boundary
        error = error_payload(action_name, exc)
        with JOB_LOCK:
            job = JOBS[job_id]
            job.status = "failed"
            job.error = error["error"]
            job.traceback = error["traceback"]
            if job.error and job.error not in job.log_text:
                if job.log_text and not job.log_text.endswith("\n"):
                    job.log_text += "\n"
                job.log_text += f"\n[error]\n{job.error}\n"
            job.finished_at = datetime.now(timezone.utc).isoformat()


def start_job(action_name: str, label: str):
    runner = STREAMING_ACTIONS[action_name]
    job_id = uuid.uuid4().hex
    job = JobState(job_id=job_id, action=action_name, label=label)
    with JOB_LOCK:
        JOBS[job_id] = job

    thread = threading.Thread(target=run_job, args=(job_id, action_name, label, runner), daemon=True)
    thread.start()
    return jsonify({"ok": True, "job_id": job_id, "action": action_name, "label": label, "status": "running"}), 202
