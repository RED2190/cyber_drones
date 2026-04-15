#!/usr/bin/env python3
"""Собрать sitl.env из docker/.env (ADMIN_* / DOCKER_NETWORK / MQTT_PORT)."""
from __future__ import annotations

import argparse
import pathlib


def parse_env(path: pathlib.Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        data[key.strip()] = val.strip()
    return data


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("docker_env", type=pathlib.Path, help="Путь к docker/.env (например cyber_drons/docker/.env)")
    p.add_argument("-o", "--out", type=pathlib.Path, default=pathlib.Path("sitl.env"))
    args = p.parse_args()
    d = parse_env(args.docker_env)
    u = d.get("ADMIN_USER", "admin")
    pw = d.get("ADMIN_PASSWORD", "")
    dn = d.get("DOCKER_NETWORK", "drones_net")
    mp = d.get("MQTT_PORT", "1883")

    def q(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    out = f"""# Сгенерировано из {args.docker_env.name} — не править вручную или перегенерируйте make sitl-env
DOCKER_NETWORK={dn}
BROKER_BACKEND=mqtt
MQTT_HOST=mosquitto
MQTT_PORT={mp}
MQTT_QOS=1
MQTT_USERNAME={u}
MQTT_PASSWORD="{q(pw)}"
REDIS_URL=redis://sitl_redis:6379
POSITION_REQUEST_TOPIC=sitl.telemetry.request
POSITION_RESPONSE_TOPIC=sitl.telemetry.response
KAFKA_SERVERS=kafka:29092
"""
    args.out.write_text(out, encoding="utf-8")
    print(f"Записано: {args.out}")


if __name__ == "__main__":
    main()
