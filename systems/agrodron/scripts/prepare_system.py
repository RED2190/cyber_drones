#!/usr/bin/env python3
"""
Сборка: брокер из <корень монорепо>/docker/docker-compose.yml + docker-compose этой системы
→ systems/agrodron/.generated/

Корень монорепозитория ищется подъёмом от этого файла по наличию docker/docker-compose.yml
(в каталоге дронов папку docker/ не держим — только в корне монорепо).

Пример:

    python systems/agrodron/scripts/prepare_system.py systems/agrodron
"""
from __future__ import annotations

import os
import sys
from copy import deepcopy
from pathlib import Path

import yaml


def resolve_monorepo_root() -> Path:
    """Корень монорепозитория: каталог, где есть docker/docker-compose.yml."""
    start = Path(__file__).resolve().parent
    for d in [start, *start.parents]:
        if (d / "docker" / "docker-compose.yml").is_file():
            return d
    return start.parent


def to_env_prefix(name: str) -> str:
    """Convert service/component name to ENV-safe prefix."""
    return "".join(ch if ch.isalnum() else "_" for ch in name).upper()


def parse_env_file(path: Path) -> dict:
    env = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def write_env_file(path: Path, env: dict):
    """Write env dict to file. Values containing \" or newlines are quoted and escaped."""
    with open(path, "w") as f:
        for key, value in env.items():
            s = str(value)
            if '"' in s or "\n" in s or "\\" in s:
                escaped = s.replace("\\", "\\\\").replace('"', '\\"')
                f.write(f'{key}="{escaped}"\n')
            else:
                f.write(f"{key}={s}\n")


def rewrite_path(original: str, from_dir: Path, to_dir: Path) -> str:
    """Rewrite a relative path: resolve it from from_dir, then make relative to to_dir."""
    abs_path = (from_dir / original).resolve()
    return os.path.relpath(abs_path, to_dir.resolve())


def rewrite_volumes(volumes: list, from_dir: Path, to_dir: Path) -> list:
    result = []
    for vol in volumes:
        parts = vol.split(":")
        if len(parts) >= 2 and not parts[0].startswith("/") and not parts[0].startswith("$"):
            parts[0] = rewrite_path(parts[0], from_dir, to_dir)
        result.append(":".join(parts))
    return result


def prepare_system(system_dir: str) -> None:
    root = resolve_monorepo_root()
    system_path = (root / system_dir).resolve()

    if not system_path.is_dir():
        print(f"Error: system directory '{system_path}' not found", file=sys.stderr)
        sys.exit(1)

    broker_compose_path = root / "docker" / "docker-compose.yml"
    system_compose_path = system_path / "docker-compose.yml"

    for path, label in [
        (broker_compose_path, "broker compose"),
        (system_compose_path, "system compose"),
    ]:
        if not path.exists():
            print(f"Error: {label} '{path}' not found", file=sys.stderr)
            sys.exit(1)

    broker_compose = yaml.safe_load(broker_compose_path.read_text())
    system_compose = yaml.safe_load(system_compose_path.read_text())

    root_env = parse_env_file(root / "docker" / ".env")
    system_env = parse_env_file(system_path / ".env")

    # Discover components: components/ (старый layout) или src/ (agrodron)
    components_dir = (
        system_path / "components" if (system_path / "components").is_dir() else system_path / "src"
    )
    component_envs = {}
    if components_dir.is_dir():
        for comp_dir in sorted(components_dir.iterdir()):
            env_file = comp_dir / ".env"
            if comp_dir.is_dir() and env_file.exists():
                component_envs[comp_dir.name] = parse_env_file(env_file)

    output_dir = system_path / ".generated"
    output_dir.mkdir(exist_ok=True)

    # --- Build merged .env ---
    merged_env = dict(root_env)
    merged_env.update(system_env)
    suffixes = []
    for i, (comp_name, env) in enumerate(component_envs.items()):
        prefix = to_env_prefix(comp_name)
        for key, value in env.items():
            merged_env[f"{prefix}_{key}"] = value

        suffix = chr(ord("A") + i)
        suffixes.append(suffix)
        merged_env[f"COMPONENT_USER_{suffix}"] = env.get("BROKER_USER", "")
        merged_env[f"COMPONENT_PASSWORD_{suffix}"] = env.get("BROKER_PASSWORD", "")

    # SYSTEM_NAME, TOPIC_VERSION, INSTANCE_ID из системного .env
    if "SYSTEM_NAME" not in merged_env:
        merged_env["SYSTEM_NAME"] = "Agrodron"
    if "TOPIC_VERSION" not in merged_env:
        merged_env["TOPIC_VERSION"] = "v1"
    if "INSTANCE_ID" not in merged_env:
        merged_env["INSTANCE_ID"] = "Agrodron001"

    # Подставляем SYSTEM_NAME в политики сразу, чтобы в .env не зависеть от порядка переменных при source
    sys_name = merged_env.get("SYSTEM_NAME", "Agrodron")
    topic_ver = merged_env.get("TOPIC_VERSION", "v1")
    instance_id = merged_env.get("INSTANCE_ID", "Agrodron001")
    topic_prefix = f"{topic_ver}.{sys_name}.{instance_id}"

    ext_substitutions = {
        "${SYSTEM_NAME}": topic_prefix,
        "$${SYSTEM_NAME}": topic_prefix,
        "$SYSTEM_NAME": topic_prefix,
        "${ORVD_TOPIC}": merged_env.get("ORVD_TOPIC", ""),
        "${NUS_TOPIC}": merged_env.get("NUS_TOPIC", ""),
        "${DRONEPORT_TOPIC}": merged_env.get("DRONEPORT_TOPIC", ""),
        "${SITL_TOPIC}": merged_env.get("SITL_TOPIC", ""),
        "${SITL_COMMANDS_TOPIC}": merged_env.get("SITL_COMMANDS_TOPIC", ""),
        "${SITL_TELEMETRY_REQUEST_TOPIC}": merged_env.get("SITL_TELEMETRY_REQUEST_TOPIC", ""),
        "${SITL_VERIFIER_HOME_TOPIC}": merged_env.get("SITL_VERIFIER_HOME_TOPIC", "sitl-drone-home"),
    }
    policy_substitutions = dict(ext_substitutions)
    for key in list(merged_env.keys()):
        if "SECURITY_POLICIES" in key and isinstance(merged_env.get(key), str):
            val = merged_env[key]
            for placeholder, replacement in policy_substitutions.items():
                val = val.replace(placeholder, replacement)
            merged_env[key] = val

    # Адреса брокера для хоста (интеграционные тесты подключаются с хоста к контейнеру)
    if "MQTT_BROKER" not in merged_env:
        merged_env["MQTT_BROKER"] = "localhost"
    if "KAFKA_BOOTSTRAP_SERVERS" not in merged_env:
        merged_env["KAFKA_BOOTSTRAP_SERVERS"] = "localhost:9092"
    # Учётные данные для хоста: интеграционные тесты подключаются к MQTT как admin
    if "BROKER_USER" not in merged_env:
        merged_env["BROKER_USER"] = merged_env.get("ADMIN_USER", "admin")
    if "BROKER_PASSWORD" not in merged_env:
        merged_env["BROKER_PASSWORD"] = merged_env.get("ADMIN_PASSWORD", "")

    # --- Rewrite broker volume paths ---
    broker_dir = broker_compose_path.parent
    broker_services = deepcopy(broker_compose.get("services", {}))
    for svc_name, svc in broker_services.items():
        if "volumes" in svc:
            svc["volumes"] = rewrite_volumes(svc["volumes"], broker_dir, output_dir)

        # Update broker env: replace hardcoded COMPONENT_USER_* with discovered ones
        env_block = svc.get("environment", {})
        if isinstance(env_block, list):
            new_env = {}
            for item in env_block:
                k, _, v = item.partition("=")
                new_env[k.strip()] = v.strip()
            env_block = new_env

        keys_to_remove = [
            k
            for k in env_block
            if k.startswith("COMPONENT_USER_") or k.startswith("COMPONENT_PASSWORD_")
        ]
        for k in keys_to_remove:
            del env_block[k]

        for suffix in suffixes:
            env_block[f"COMPONENT_USER_{suffix}"] = f"${{COMPONENT_USER_{suffix}:-}}"
            env_block[f"COMPONENT_PASSWORD_{suffix}"] = f"${{COMPONENT_PASSWORD_{suffix}:-}}"

        svc["environment"] = env_block

    # --- Rewrite component build paths ---
    system_dir_abs = system_compose_path.parent
    component_services = deepcopy(system_compose.get("services", {}))
    for svc_name, svc in component_services.items():
        if "build" in svc:
            build = svc["build"]
            if isinstance(build, dict) and "context" in build:
                build["context"] = rewrite_path(build["context"], system_dir_abs, output_dir)

        # Add depends_on for broker health checks
        svc["depends_on"] = {
            "kafka": {"condition": "service_healthy", "required": False},
            "mosquitto": {"condition": "service_healthy", "required": False},
        }

    # --- Merge into single compose ---
    merged = {
        "name": "drones",
        "services": {},
        "networks": {
            "drones_net": {
                "driver": "bridge",
                "name": "${DOCKER_NETWORK:-drones_net}",
            }
        },
    }

    for svc_name, svc in broker_services.items():
        merged["services"][svc_name] = svc

    for svc_name, svc in component_services.items():
        merged["services"][svc_name] = svc

    # --- Merge top-level volumes (for persistent component storage) ---
    broker_volumes = deepcopy(broker_compose.get("volumes", {})) or {}
    system_volumes = deepcopy(system_compose.get("volumes", {})) or {}
    if broker_volumes or system_volumes:
        merged["volumes"] = {}
        merged["volumes"].update(broker_volumes)
        merged["volumes"].update(system_volumes)

    # --- Write output ---
    compose_out = output_dir / "docker-compose.yml"
    env_out = output_dir / ".env"

    system_dir_arg = system_dir.strip() or "."
    with open(compose_out, "w") as f:
        f.write(
            "# AUTO-GENERATED by scripts/prepare_system.py\n"
            "# Do not edit manually. Re-run from monorepo root, e.g.:\n"
            "#   python scripts/prepare_system.py "
            f"{system_dir_arg}\n"
        )
        yaml.dump(merged, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    write_env_file(env_out, merged_env)

    print(f"Generated: {compose_out}")
    print(f"Generated: {env_out}")
    print(f"Components: {', '.join(component_envs.keys())}")
    print(f"Credentials mapped: {', '.join(f'COMPONENT_USER_{s}' for s in suffixes)}")
    print()
    print("To start:")
    broker_type = merged_env.get("BROKER_TYPE", "kafka")
    print(
        f"  docker compose -f {compose_out} --env-file {env_out} "
        f"--profile {broker_type} up -d --build"
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(
            "Usage: python scripts/prepare_system.py <system_dir>\n"
            "Example: python systems/agrodron/scripts/prepare_system.py systems/agrodron",
            file=sys.stderr,
        )
        sys.exit(1)
    prepare_system(sys.argv[1])
