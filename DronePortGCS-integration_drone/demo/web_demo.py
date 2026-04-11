from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from flask import Flask, jsonify, render_template, request, send_from_directory

from demo.interactive_demo import DockerInteractiveDemo, default_task_waypoints


app = Flask(__name__, template_folder="templates")
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
demo = DockerInteractiveDemo(client_id="web_demo")
ROOT = Path(__file__).resolve().parents[1]
GCS_DIAGRAMS_DIR = ROOT / "systems" / "gcs" / "docs" / "diagrams"
GCS_C4_DIR = ROOT / "systems" / "gcs" / "docs" / "c4"


@dataclass
class JobState:
    job_id: str
    action: str
    label: str
    status: str = "running"
    log_text: str = ""
    result: Any = None
    result_text: str = ""
    error: str = ""
    traceback: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: Optional[str] = None


JOB_LOCK = threading.Lock()
JOBS: Dict[str, JobState] = {}
STREAMING_ACTIONS: Dict[str, Callable[[Callable[[str], None]], Any]] = {
    "prepare": demo.prepare_systems_stream,
    "broker-up": demo.broker_up_stream,
    "gcs-up": demo.gcs_up_stream,
    "gcs-interactive-up": demo.gcs_interactive_up_stream,
    "drone-port-up": demo.drone_port_up_stream,
}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() not in {"0", "false", "no"}


def _bootstrap_gcs_stack() -> None:
    auto_bootstrap = _env_bool("GCS_WEB_AUTO_BOOTSTRAP", True)
    if not auto_bootstrap:
        print("[bootstrap] Skipped (GCS_WEB_AUTO_BOOTSTRAP=0). Подключение к уже поднятому брокеру/GCS/DronePort…")
        try:
            demo.connect_bus()
            demo.wait_until_ready(timeout=120)
            print("[bootstrap] ✓ Шина подключена.")
        except Exception as e:
            print(f"[bootstrap] ✗ Подключение не удалось: {e}")
            print("[bootstrap] UI всё равно запущен — проверьте broker и контейнеры.")
        return

    print("[bootstrap] Starting stack: broker → GCS → DronePort")
    try:
        # 1. Подготовка систем (генерация docker-compose.yml)
        print("[bootstrap] Step 1/5: Preparing systems... ")
        demo.prepare_systems_stream(on_output=lambda chunk: print(chunk, end=""))
        
        # 2. 🔥 Запуск брокера (ОДИН РАЗ для всех систем)
        print("\n[bootstrap] Step 2/5: Starting broker (shared)... ")
        demo.broker_up_stream(on_output=lambda chunk: print(chunk, end=""))
        demo.wait_for_broker(timeout=90)  # 🔥 Увеличенный таймаут
        
        # 3. Запуск GCS
        print("\n[bootstrap] Step 3/5: Starting GCS... ")
        demo.gcs_up_stream(on_output=lambda chunk: print(chunk, end=""))
        
        # 4. 🔥 Запуск DronePort (без брокера!)
        print("\n[bootstrap] Step 4/5: Starting DronePort (no broker)... ")
        demo.drone_port_up_stream(on_output=lambda chunk: print(chunk, end=""))
        
        # 5. Подключение и проверка готовности
        print("\n[bootstrap] Step 5/5: Connecting and waiting for readiness... ")
        demo.connect_bus()
        demo.wait_until_ready(timeout=180)  # 🔥 Увеличенный таймаут для DronePort
        
        print("[bootstrap] ✓ All components ready (shared broker).")
        
    except Exception as e:
        print(f"[bootstrap] ✗ Failed: {e}")
        print(f"[bootstrap] Traceback: {traceback.format_exc()}")
        print("[bootstrap] Web UI exposed, components may be unavailable.")

def _read_git_file(ref: str, path: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "show", f"{ref}:{path}"],
            cwd=str(ROOT),
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return ""


def _discover_bind_urls(host: str, port: int) -> list[str]:
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


def _clean_md(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
    cleaned = cleaned.replace("`", "")
    return cleaned.strip()


def _extract_between(text: str, start_marker: str, end_marker: str | None = None) -> str:
    start = text.find(start_marker)
    if start == -1:
        return ""
    start += len(start_marker)
    if end_marker:
        end = text.find(end_marker, start)
        if end != -1:
            return text[start:end].strip()
    return text[start:].strip()


def _parse_md_table(section_text: str) -> Dict[str, Any]:
    lines = [line.strip() for line in section_text.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        return {"headers": [], "rows": []}
    headers = [_clean_md(cell) for cell in lines[0].strip("|").split("|")]
    rows = []
    for line in lines[2:]:
        rows.append([_clean_md(cell) for cell in line.strip("|").split("|")])
    return {"headers": headers, "rows": rows}


def _parse_bullets(section_text: str) -> list[str]:
    items = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("* "):
            items.append(_clean_md(stripped[2:]))
        elif stripped.startswith("🔴 "):
            items.append(_clean_md(stripped))
    return items


def _parse_threats(section_text: str) -> list[Dict[str, Any]]:
    threats = []
    parts = section_text.split("### ")
    for part in parts[1:]:
        lines = part.splitlines()
        title = _clean_md(lines[0])
        description = _extract_between(part, "**Описание:**", "**Нарушаемые цели:**")
        violated = _extract_between(part, "**Нарушаемые цели:**", "**Критичность:**")
        criticality = _extract_between(part, "**Критичность:**", "**Контрмеры:**")
        countermeasures = _parse_bullets(_extract_between(part, "**Контрмеры:**", "---"))
        threats.append(
            {
                "title": title,
                "description": _clean_md(description),
                "violated_goals": [line.strip() for line in violated.splitlines() if line.strip()],
                "criticality": _clean_md(criticality),
                "countermeasures": countermeasures,
            }
        )
    return threats


def _parse_security_analysis(text: str) -> Dict[str, Any]:
    if not text:
        return {}

    assets_section = _extract_between(text, "### 1.1 Идентификация активов", "### 1.2 Оценка уровня ущерба")
    damage_section = _extract_between(text, "### 1.2 Оценка уровня ущерба", "### 1.3 Приемлемость риска")
    risk_section = _extract_between(text, "### 1.3 Приемлемость риска", "### Вывод по пункту 1")
    conclusion_section = _extract_between(text, "### Вывод по пункту 1", "## Пункт 2.")
    goals_section = _extract_between(text, "### 4.1 Цели безопасности", "# 4.2 Предположения безопасности")
    assumptions_section = _extract_between(text, "# 4.2 Предположения безопасности", "## Пункт 5. Моделирование угроз")
    threats_section = _extract_between(text, "## Пункт 5. Моделирование угроз", "## Пункт 6. Домен доверия")
    trust_section = _extract_between(text, "## Пункт 6. Домен доверия")

    damage_scale_section = _extract_between(damage_section, "Шкала оценки:", "##### Таблица оценки активов НУС")
    damage_assets_section = _extract_between(damage_section, "##### Таблица оценки активов НУС")
    critical_assets_section = _extract_between(conclusion_section, "Наиболее критичные активы системы:", "Их компрометация может привести к:")
    critical_effects_section = _extract_between(conclusion_section, "Их компрометация может привести к:")

    return {
        "assets": _parse_md_table(assets_section),
        "damage_scale": _parse_md_table(damage_scale_section),
        "damage_assets": _parse_md_table(damage_assets_section),
        "risk_acceptance": _parse_md_table(risk_section),
        "critical_assets": _parse_bullets(critical_assets_section),
        "critical_effects": _parse_bullets(critical_effects_section),
        "security_goals": _parse_md_table(goals_section),
        "security_assumptions": _parse_md_table(assumptions_section),
        "threats": _parse_threats(threats_section),
        "trust_domain": _parse_md_table(trust_section),
    }


def _json_payload() -> Dict[str, Any]:
    return request.get_json(silent=True) or {}


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _serialize(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


def _error_payload(action_name: str, exc: Exception) -> Dict[str, Any]:
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


def _execute(action_name: str, func):
    try:
        result = func()
        return jsonify({"ok": True, "action": action_name, "result": result, "result_text": _serialize(result)})
    except Exception as exc:  # pragma: no cover - defensive boundary for UI
        import traceback
        print(f"[ERROR] {action_name}: {traceback.format_exc()}")
        return jsonify(_error_payload(action_name, exc)), 500


def _append_job_log(job_id: str, chunk: str) -> None:
    with JOB_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return
        job.log_text += chunk


def _job_payload(job: JobState) -> Dict[str, Any]:
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


def _run_job(job_id: str, action_name: str, label: str, runner: Callable[[Callable[[str], None]], Any]) -> None:
    def on_output(chunk: str) -> None:
        _append_job_log(job_id, chunk)

    try:
        result = runner(on_output)
        with JOB_LOCK:
            job = JOBS[job_id]
            job.status = "succeeded"
            job.result = result
            job.result_text = _serialize(result)
            if job.result_text and job.result_text not in job.log_text:
                if job.log_text and not job.log_text.endswith("\n"):
                    job.log_text += "\n"
                job.log_text += f"\n[result]\n{job.result_text}\n"
            job.finished_at = datetime.now(timezone.utc).isoformat()
    except Exception as exc:  # pragma: no cover - background boundary
        error = _error_payload(action_name, exc)
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


def _start_job(action_name: str, label: str):
    runner = STREAMING_ACTIONS[action_name]
    job_id = uuid.uuid4().hex
    job = JobState(job_id=job_id, action=action_name, label=label)
    with JOB_LOCK:
        JOBS[job_id] = job

    thread = threading.Thread(target=_run_job, args=(job_id, action_name, label, runner), daemon=True)
    thread.start()
    return jsonify({"ok": True, "job_id": job_id, "action": action_name, "label": label, "status": "running"}), 202


@app.get("/")
def index():
    diagrams = []
    if GCS_DIAGRAMS_DIR.exists():
        for path in sorted(GCS_DIAGRAMS_DIR.iterdir()):
            if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}:
                continue
            diagrams.append(
                {
                    "name": path.name,
                    "title": path.stem.replace("_", " "),
                    "url": f"/gcs-diagrams/{path.name}",
                }
            )
    security_artifacts = []
    if GCS_C4_DIR.exists():
        for filename in ("C2_Containers_Trust.puml", "C1_Context.puml", "C2_Containers.puml", "README.md"):
            path = GCS_C4_DIR / filename
            if path.exists():
                security_artifacts.append(
                    {
                        "name": path.name,
                        "title": path.stem.replace("_", " "),
                        "url": f"/gcs-c4/{path.name}",
                    }
                )
    remote_security_analysis = _read_git_file("origin/security-analysis", "docs/GCS_SECURITY_ANALYSIS.md")
    security_analysis = _parse_security_analysis(remote_security_analysis)
    return render_template(
        "web_demo.html",
        diagrams=diagrams,
        security_artifacts=security_artifacts,
        security_analysis=security_analysis,
    )


@app.get("/gcs-diagrams/<path:filename>")
def gcs_diagrams(filename: str):
    return send_from_directory(GCS_DIAGRAMS_DIR, filename)


@app.get("/gcs-c4/<path:filename>")
def gcs_c4(filename: str):
    return send_from_directory(GCS_C4_DIR, filename)


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.get("/api/config")
def config():
    return jsonify(
        {
            "default_waypoints": default_task_waypoints(),
            "client_id": demo.client_id,
        }
    )


@app.post("/api/jobs/<action_name>")
def start_job(action_name: str):
    if action_name not in STREAMING_ACTIONS:
        return jsonify({"ok": False, "error": f"streaming action is not supported: {action_name}"}), 404
    payload = _json_payload()
    label = _optional_text(payload.get("label")) or action_name
    return _start_job(action_name, label)


@app.get("/api/jobs/<job_id>")
def get_job(job_id: str):
    with JOB_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return jsonify({"ok": False, "error": f"job not found: {job_id}"}), 404
        return jsonify(_job_payload(job))


@app.post("/api/action/broker-down")
def broker_down():
    return _execute("broker-down", demo.broker_down)


@app.post("/api/action/gcs-down")
def gcs_down():
    return _execute("gcs-down", demo.gcs_down)


@app.post("/api/action/gcs-interactive-down")
def gcs_interactive_down():
    return _execute("gcs-interactive-down", demo.gcs_interactive_down)


@app.get("/api/action/ps")
def ps():
    return _execute("ps", demo.gcs_ps)


@app.post("/api/action/landing")
def landing():
    payload = _json_payload()

    def run():
        return demo.request_landing(
            drone_id=_optional_text(payload.get("drone_id")) or "drone-demo-1",
            model=_optional_text(payload.get("model")) or "DemoCopter-X",
        )

    return _execute("landing", run)


@app.post("/api/action/charging")
def charging():
    payload = _json_payload()

    def run():
        battery = float(payload.get("battery", 30))
        return demo.request_charging(
            drone_id=_optional_text(payload.get("drone_id")) or "drone-demo-1",
            battery=battery,
        )

    return _execute("charging", run)


@app.post("/api/action/takeoff")
def takeoff():
    payload = _json_payload()

    def run():
        return demo.request_takeoff(_optional_text(payload.get("drone_id")) or "drone-demo-1")

    return _execute("takeoff", run)


@app.post("/api/action/submit-task")
def submit_task():
    payload = _json_payload()

    def run():
        waypoints = payload.get("waypoints")
        return demo.submit_task(waypoints=waypoints)

    return _execute("submit-task", run)


@app.post("/api/action/assign-task")
def assign_task():
    payload = _json_payload()

    def run():
        mission_id = _optional_text(payload.get("mission_id"))
        if not mission_id:
            raise ValueError("mission_id is required")
        return demo.assign_task(
            mission_id=mission_id,
            drone_id=_optional_text(payload.get("drone_id")) or "drone-demo-1",
        )

    return _execute("assign-task", run)


@app.post("/api/action/start-task")
def start_task():
    payload = _json_payload()

    def run():
        mission_id = _optional_text(payload.get("mission_id"))
        if not mission_id:
            raise ValueError("mission_id is required")
        return demo.start_task(
            mission_id=mission_id,
            drone_id=_optional_text(payload.get("drone_id")) or "drone-demo-1",
        )

    return _execute("start-task", run)


@app.post("/api/action/mission")
def mission():
    payload = _json_payload()

    def run():
        mission_id = _optional_text(payload.get("mission_id"))
        if not mission_id:
            raise ValueError("mission_id is required")
        return demo.get_mission(mission_id)

    return _execute("mission", run)


@app.post("/api/action/drone-state")
def drone_state():
    payload = _json_payload()

    def run():
        drone_id = _optional_text(payload.get("drone_id"))
        if not drone_id:
            raise ValueError("drone_id is required")
        return demo.get_drone_state(drone_id)

    return _execute("drone-state", run)


@app.post("/api/action/snapshot")
def snapshot():
    payload = _json_payload()

    def run():
        return demo.gcs_snapshot(
            drone_id=_optional_text(payload.get("drone_id")) or "drone-demo-1",
            mission_id=_optional_text(payload.get("mission_id")),
        )

    return _execute("snapshot", run)


@app.post("/api/action/drone-port-up")
def drone_port_up():
    """Запуск DronePort"""
    def run():
        return demo.drone_port_up()
    return _execute("drone-port-up", run)


@app.post("/api/action/drone-port-down")
def drone_port_down():
    """Остановка DronePort"""
    def run():
        return demo.drone_port_down()
    return _execute("drone-port-down", run)


@app.post("/api/action/drone-port-status")
def drone_port_status():
    """Статус DronePort"""
    def run():
        result = demo.ps()
        # Если результат - строка, оборачиваем в словарь для корректного JSON
        if isinstance(result, str):
            return {"status_output": result}
        return result
    return _execute("drone-port-status", run)


@app.post("/api/action/ports-status")
def ports_status():
    """Получить статус портов дронопорта"""
    def run():
        result = demo.get_ports()
        if result is None:
            # Возвращаем демо-данные если DronePort не запущен
            return {
                "payload": {
                    "ports": [
                        {"id": "port-1", "status": "occupied", "drone": {"type": "DemoCopter-X", "id": "drone-demo-1"}},
                        {"id": "port-2", "status": "available", "drone": None},
                        {"id": "port-3", "status": "occupied", "drone": {"type": "Cargo-Drone-A", "id": "drone-demo-2"}},
                        {"id": "port-4", "status": "available", "drone": None},
                        {"id": "port-5", "status": "available", "drone": None},
                        {"id": "port-6", "status": "available", "drone": None}
                    ]
                }
            }
        return result
    return _execute("ports-status", run)


@app.post("/api/action/available-drones")
def available_drones():
    """Получить список доступных дронов в дронопорте"""
    def run():
        result = demo.get_available_droneport_drones()
        if result is None:
            return {"error": "Не удалось получить список дронов. Убедитесь, что DronePort запущен."}
        return result
    return _execute("available-drones", run)


@app.post("/api/action/registry-record")
def registry_record():
    """Получить запись в реестре дронов"""
    payload = _json_payload()
    def run():
        drone_id = _optional_text(payload.get("drone_id")) or "drone-demo-1"
        result = demo.get_drone_registry_record(drone_id)
        if result is None:
            return {"error": f"Не удалось получить запись для дрона {drone_id}. Убедитесь, что DronePort запущен и дрон зарегистрирован."}
        return result
    return _execute("registry-record", run)


# В web_demo.py найдите существующий эндпоинт @app.post("/api/action/logs") и обновите:
@app.post("/api/action/logs")
def logs():
    payload = _json_payload()

    def run():
        stack = payload.get("stack", "broker")
        service = _optional_text(payload.get("service"))
        tail = int(payload.get("tail", 100))
        if stack not in {"broker", "gcs", "drone_port"}:  # Добавлено "drone_port"
            raise ValueError("stack must be one of: broker, gcs, drone_port")
        return demo.logs(stack=stack, service=service, tail=tail)

    return _execute("logs", run)


if __name__ == "__main__":
    app.jinja_env.auto_reload = True
    _bootstrap_gcs_stack()
    host = os.environ.get("GCS_WEB_HOST", "0.0.0.0")
    port = int(os.environ.get("GCS_WEB_PORT", "8000"))
    debug = _env_bool("GCS_WEB_DEBUG", False)

    print("[web] Interface is available at:")
    for url in _discover_bind_urls(host, port):
        print(f"[web]   {url}")

    app.run(host=host, port=port, debug=debug, threaded=True)