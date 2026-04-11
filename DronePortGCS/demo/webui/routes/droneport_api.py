from __future__ import annotations

from flask import Blueprint

from demo.webui.runtime import demo
from demo.webui.utils import execute, json_payload, optional_text


droneport_api = Blueprint("droneport_api", __name__)


@droneport_api.post("/api/action/drone-port-up")
def drone_port_up():
    return execute("drone-port-up", demo.drone_port_up)


@droneport_api.post("/api/action/drone-port-down")
def drone_port_down():
    return execute("drone-port-down", demo.drone_port_down)


@droneport_api.post("/api/action/drone-port-status")
def drone_port_status():
    return execute("drone-port-status", demo.drone_port_health)


@droneport_api.post("/api/action/ports-status")
def ports_status():
    def run():
        result = demo.get_ports()
        if result is None:
            return {
                "error": (
                    "Не удалось получить список портов от DronePort. "
                    "Убедитесь, что DronePort запущен."
                )
            }
        return result

    return execute("ports-status", run)


@droneport_api.post("/api/action/available-drones")
def available_drones():
    def run():
        result = demo.get_available_droneport_drones()
        if result is None:
            return {"error": "Не удалось получить список дронов. Убедитесь, что DronePort запущен."}
        return result

    return execute("available-drones", run)


@droneport_api.post("/api/action/registry-record")
def registry_record():
    payload = json_payload()

    def run():
        drone_id = optional_text(payload.get("drone_id")) or "drone-demo-1"
        result = demo.get_drone_registry_record(drone_id)
        if result is None:
            return {
                "error": (
                    f"Не удалось получить запись для дрона {drone_id}. "
                    "Убедитесь, что DronePort запущен и дрон зарегистрирован."
                )
            }
        return result

    return execute("registry-record", run)
