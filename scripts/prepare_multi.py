#!/usr/bin/env python3
"""
Генератор единого docker-compose для нескольких систем.

Особенности:
- один broker-стек (kafka/mosquitto) из docker/docker-compose.yml;
- обязательный список систем через --systems;
- строгая проверка конфликтов host-портов (всегда ошибка);
- проверка, что сервисы подключены к общей сети drones_net;
- rewrite относительных build/volume путей в output директорию.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


def parse_env_file(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            value = value.strip()
            # Strip surrounding quotes and unescape \" inside
            if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
                value = value[1:-1].replace('\\"', '"')
            else:
                value = value.replace('\\"', '"')
            env[key.strip()] = value
    return env


def write_env_file(path: Path, env: Dict[str, str]) -> None:
    with open(path, "w") as f:
        for key, value in env.items():
            f.write(f"{key}={value}\n")


def rewrite_path(original: str, from_dir: Path, to_dir: Path) -> str:
    # normpath instead of resolve to avoid following symlinks
    abs_path = os.path.normpath(from_dir / original)
    return os.path.relpath(abs_path, os.path.normpath(to_dir))


def rewrite_volumes(volumes: List[str], from_dir: Path, to_dir: Path) -> List[str]:
    def should_rewrite_source(source: str) -> bool:
        """
        Rewrite only bind-mount like sources.
        Keep named volumes (e.g. postgres_data) untouched.
        """
        if not source or source.startswith("$"):
            return False
        if source.startswith(("/", "./", "../", "~")):
            return True
        # Relative host path like "data/logs" should be rewritten.
        # Named volumes typically don't contain a path separator.
        return "/" in source or "\\" in source

    result = []
    for vol in volumes:
        parts = vol.split(":")
        if len(parts) >= 2 and should_rewrite_source(parts[0]):
            parts[0] = rewrite_path(parts[0], from_dir, to_dir)
        result.append(":".join(parts))
    return result


def env_list_to_dict(env_block: Any) -> Dict[str, str]:
    if isinstance(env_block, dict):
        return dict(env_block)
    if isinstance(env_block, list):
        out: Dict[str, str] = {}
        for item in env_block:
            k, _, v = str(item).partition("=")
            out[k.strip()] = v.strip()
        return out
    return {}


def _split_port_string(s: str) -> List[str]:
    """Split on ':' that is outside ${...} braces."""
    parts: List[str] = []
    depth = 0
    current: List[str] = []
    for ch in s:
        if ch == "$" or (ch == "{" and current and current[-1] == "$"):
            current.append(ch)
            if ch == "{":
                depth += 1
            continue
        if ch == "}" and depth > 0:
            depth -= 1
            current.append(ch)
            continue
        if ch == ":" and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(ch)
    parts.append("".join(current))
    return parts


def parse_port_mapping(mapping: Any) -> Optional[Tuple[str, str]]:
    """
    Возвращает (host_port_expr, protocol) для short syntax.
    Только host-порты участвуют в конфликте.
    """
    if isinstance(mapping, int):
        return None
    if isinstance(mapping, dict):
        published = mapping.get("published")
        protocol = str(mapping.get("protocol", "tcp"))
        if published is None:
            return None
        return str(published), protocol

    s = str(mapping).strip()
    if not s:
        return None

    if "/" in s:
        s, protocol = s.rsplit("/", 1)
    else:
        protocol = "tcp"

    parts = _split_port_string(s)
    if len(parts) == 1:
        return None
    if len(parts) == 2:
        host = parts[0]
    else:
        host = parts[-2]

    if not host:
        return None
    return host, protocol


def validate_ports(services: Dict[str, Dict[str, Any]]) -> None:
    used: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
    for svc_name, svc in services.items():
        for port in svc.get("ports", []) or []:
            parsed = parse_port_mapping(port)
            if not parsed:
                continue
            key = parsed
            used.setdefault(key, []).append((svc_name, str(port)))

    conflicts = {k: v for k, v in used.items() if len(v) > 1}
    if not conflicts:
        return

    lines = ["Port conflict detected:"]
    for (host, proto), owners in sorted(conflicts.items()):
        lines.append(f"- {host}/{proto}:")
        for svc_name, mapping in owners:
            lines.append(f"  - service={svc_name} mapping={mapping}")
    raise RuntimeError("\n".join(lines))


def ensure_common_network(svc: Dict[str, Any]) -> None:
    networks = svc.get("networks")
    if not networks:
        svc["networks"] = ["drones_net"]
        return

    if isinstance(networks, dict):
        if "drones_net" not in networks:
            raise RuntimeError(
                "Service has explicit networks without drones_net. "
                f"networks={list(networks.keys())}"
            )
        return

    if isinstance(networks, list):
        if "drones_net" not in networks:
            raise RuntimeError(f"Service networks must include drones_net: {networks}")
        return

    raise RuntimeError(f"Unsupported networks type: {type(networks)}")


def env_key_looks_like_hostname(env_key: str) -> bool:
    """
    Return True for env keys that are expected to contain a hostname value.
    This protects credentials/ids from accidental service-name rewrites.
    """
    key = env_key.upper()
    explicit_host_keys = {
        "KAFKA_BROKER",
        "KAFKA_BOOTSTRAP_SERVERS",
        "MQTT_BROKER",
        "REDIS_HOST",
        "POSTGRES_HOST",
        "DB_HOST",
        "DATABASE_HOST",
        "MYSQL_HOST",
        "MONGO_HOST",
        "HOST",
        "HOSTNAME",
    }
    return (
        key in explicit_host_keys
        or key.endswith("_HOST")
        or key.endswith("_HOSTNAME")
    )


def normalize_system_path(root: Path, system_name: str) -> Path:
    if system_name.startswith("systems/"):
        p = root / system_name
    else:
        p = root / "systems" / system_name
    return p


def detect_system_compose_path(system_path: Path) -> Path:
    """Support both docker-compose.yml and docker-compose.yaml."""
    candidates = (
        system_path / "docker-compose.yml",
        system_path / "docker-compose.yaml",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise RuntimeError(
        f"System compose not found: expected one of {candidates[0]} or {candidates[1]}"
    )


def prepare_multi(systems: List[str], output: Optional[str]) -> None:
    root = Path(__file__).resolve().parent.parent
    broker_compose_path = root / "docker" / "docker-compose.yml"
    broker_env_path = root / "docker" / ".env"
    if not broker_compose_path.exists():
        raise RuntimeError(f"Broker compose not found: {broker_compose_path}")

    system_paths = []
    for item in systems:
        path = normalize_system_path(root, item)
        if not path.is_dir():
            raise RuntimeError(f"System dir not found: {path}")
        compose = detect_system_compose_path(path)
        system_paths.append(path)

    output_dir = (root / output).resolve() if output else (root / ".generated" / "multi").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    broker_compose = yaml.safe_load(broker_compose_path.read_text()) or {}
    broker_services = deepcopy(broker_compose.get("services", {}))

    # rewrite broker volume paths относительно output директории
    broker_dir = broker_compose_path.parent
    for svc in broker_services.values():
        if "volumes" in svc:
            svc["volumes"] = rewrite_volumes(svc["volumes"], broker_dir, output_dir)

    merged_services: Dict[str, Dict[str, Any]] = {}
    merged_services.update(broker_services)
    merged_volumes: Dict[str, Any] = {}

    # Нормализуем redis как общий сервис с именем redis, если он есть хотя бы в одной системе.
    has_global_redis = "redis" in merged_services

    for sys_path in system_paths:
        sys_compose_path = detect_system_compose_path(sys_path)
        sys_compose = yaml.safe_load(sys_compose_path.read_text()) or {}
        sys_services = deepcopy(sys_compose.get("services", {}))
        sys_name = sys_path.name

        # SITL-module integration mode:
        # SITL upstream (ветка pure) больше не содержит дублей broker/ и sdk/
        # (3dd798b/252d998 их удалили), поэтому монтируем монорепные broker/
        # и sdk/ в build-образ через volumes — Dockerfile собирается из своего
        # context, а runtime получает монорепный broker/sdk поверх /app.
        if sys_name.lower() == "sitl-module":
            for infra_service in ("zookeeper", "kafka", "mosquitto", "redis"):
                sys_services.pop(infra_service, None)
            # Apstream SITL на ветке pure дублирует broker/ и sdk/, но не
            # доложил половину файлов (system_bus, config, messages,
            # base_component). Правильный подход — использовать монорепные
            # broker/ и sdk/ как единый источник истины и не иметь
            # дубликатов в сабмодуле. Пока SITL-команда не почистит свой
            # sdk/broker, монтируем наши поверх.
            monorepo_broker = rewrite_path("broker", root, output_dir)
            monorepo_sdk = rewrite_path("sdk", root, output_dir)
            for sitl_service_name, sitl_service in sys_services.items():
                if not sitl_service_name.startswith("sitl_"):
                    continue
                # Healthcheck в sitl_messaging обращается к redis:6379 — в общем
                # compose alias есть, но ломается при rebalance. Убираем.
                sitl_service.pop("healthcheck", None)
                svc_volumes = sitl_service.setdefault("volumes", [])
                svc_volumes.extend([
                    f"{monorepo_broker}:/app/broker:ro",
                    f"{monorepo_sdk}:/app/sdk:ro",
                ])

        # drones (deliverydron) integration mode:
        # Go-система. Build context — monorepo root (rewrite_path сам прокинет).
        # Apстрим параметризовал пути через ARG DELIVERYDRON_ROOT и
        # TOPIC_SCHEME=components, поэтому достаточно прокинуть env. Для e2e
        # подключаем только delivery_drone (один контейнер: ping/health),
        # реальный заказ всё равно летит на agrodron.
        if sys_name.lower() == "drones":
            keep_services = {"delivery_drone"}
            for s_name in list(sys_services.keys()):
                if s_name not in keep_services:
                    sys_services.pop(s_name)

        sys_volume_names = set()
        for vol_name, vol_cfg in (sys_compose.get("volumes") or {}).items():
            prefixed = f"{sys_name}_{vol_name}"
            merged_volumes[prefixed] = vol_cfg
            sys_volume_names.add(vol_name)

        # Маппинг original_name -> prefixed_name для переписывания env hostname'ов
        _GLOBAL_SERVICES = {"kafka", "mosquitto", "redis", "zookeeper"}
        svc_name_map: Dict[str, str] = {}
        for orig in sys_services:
            if orig == "redis":
                svc_name_map[orig] = "redis"
            else:
                svc_name_map[orig] = f"{sys_name.lower()}_{orig}"

        # Приоритет: если redis уже есть, локальные redis из следующих систем не добавляем.
        for original_name, svc in sys_services.items():
            svc_name = original_name

            if original_name == "redis":
                if has_global_redis:
                    continue
                has_global_redis = True
                svc_name = "redis"
            else:
                # Избегаем коллизий между системами (orchestrator, drone_manager, ...)
                # Docker требует lowercase имена сервисов
                svc_name = f"{sys_name.lower()}_{original_name}"

            # rewrite build/volumes для сервисов систем
            if "build" in svc:
                build = svc["build"]
                if isinstance(build, dict) and "context" in build:
                    build["context"] = rewrite_path(build["context"], sys_compose_path.parent, output_dir)
            if "volumes" in svc:
                svc["volumes"] = rewrite_volumes(svc["volumes"], sys_compose_path.parent, output_dir)
                rewritten = []
                for v in svc["volumes"]:
                    parts = str(v).split(":")
                    if len(parts) >= 2 and parts[0] in sys_volume_names:
                        parts[0] = f"{sys_name}_{parts[0]}"
                    rewritten.append(":".join(parts))
                svc["volumes"] = rewritten

            # Inline env_file: merge referenced .env files into environment
            # (lower priority than explicit environment vars).
            # This also enables Docker Compose variable substitution for values
            # like ${BROKER_USER:-admin} which wouldn't be interpolated in env_file.
            if "env_file" in svc:
                env_files = svc.pop("env_file")
                if isinstance(env_files, str):
                    env_files = [env_files]
                base_env: Dict[str, str] = {}
                for ef in env_files:
                    ef_path = (sys_compose_path.parent / ef).resolve()
                    base_env.update(parse_env_file(ef_path))
                explicit_env = env_list_to_dict(svc.get("environment"))
                base_env.update(explicit_env)
                svc["environment"] = base_env

            env_dict = env_list_to_dict(svc.get("environment"))
            if original_name != "redis":
                if "REDIS_HOST" in env_dict and has_global_redis:
                    env_dict["REDIS_HOST"] = "redis"

            # ----------------------------------------------------------------
            # System-specific env injections
            # ----------------------------------------------------------------
            # drone_port / gcs: топики `<system>.components.*` (избегаем коллизий).
            if sys_name.lower() == "drone_port":
                env_dict["SYSTEM_NAMESPACE"] = "drone_port"
            if sys_name.lower() == "gcs":
                env_dict["SYSTEM_NAMESPACE"] = "gcs"

            # agrodron: Kafka по умолчанию; MQTT если E2E_BROKER=mqtt (e2e-mqtt).
            if sys_name.lower() == "agrodron":
                env_dict["BROKER_TYPE"] = os.getenv("E2E_BROKER", "kafka")
                env_dict["NUS_TOPIC"] = "gcs.components.drone_manager"
                env_dict["ORVD_TOPIC"] = "systems.orvd_system"
                env_dict["DRONEPORT_TOPIC"] = "drone_port.components.drone_manager"
                # AgroDron: shim для импорта components.autopilot (см. autopilot.py).
                if original_name == "autopilot":
                    shim_path = rewrite_path(".generated/agrodron-shim/components", root, output_dir)
                    svc_volumes = svc.setdefault("volumes", [])
                    svc_volumes.append(f"{shim_path}:/app/components:ro")
                if os.getenv("E2E_BROKER") == "mqtt":
                    # MQTT-сценарий: очереди и цепочка proxy_request длиннее.
                    env_dict["NAVIGATION_POLL_INTERVAL_S"] = "2.0"
                    env_dict["AUTOPILOT_REQUEST_TIMEOUT_S"] = "30"
                    env_dict["SECURITY_MONITOR_PROXY_REQUEST_TIMEOUT_S"] = "25"
                else:
                    env_dict["NAVIGATION_POLL_INTERVAL_S"] = "1.0"
                    env_dict["SECURITY_MONITOR_PROXY_REQUEST_TIMEOUT_S"] = "15.0"
                    env_dict["AUTOPILOT_REQUEST_TIMEOUT_S"] = "20"
                # One shared drone_id across AgroDron, DronePort and SITL.
                env_dict["INSTANCE_ID"] = "drone_001"
                env_dict["SITL_TOPIC"] = "sitl.telemetry.request"
                env_dict["SITL_COMMANDS_TOPIC"] = "sitl.commands"
                env_dict["SITL_TELEMETRY_REQUEST_TOPIC"] = "sitl.telemetry.request"
                env_dict["SITL_VERIFIER_HOME_TOPIC"] = "sitl-drone-home"

                # Inject SECURITY_POLICIES for security_monitor from monorepo config.
                if original_name == "security_monitor":
                    _policies_file = root / "config" / "agrodron" / "security_policies.json"
                    if _policies_file.exists():
                        env_dict["SECURITY_POLICIES"] = _policies_file.read_text().strip()

                # Resolve placeholders in SECURITY_POLICIES and append e2e_test_host rules.
                if original_name == "security_monitor" and env_dict.get("SECURITY_POLICIES"):
                    _raw = env_dict.get("SYSTEM_NAME", "Agrodron")
                    _system_name = "Agrodron" if "${" in str(_raw) else str(_raw)
                    _A = f"components.{_system_name}"
                    _subs = {
                        "${SYSTEM_NAME}": _A,
                        "$SYSTEM_NAME":   _A,
                        "${NUS_TOPIC}":              env_dict.get("NUS_TOPIC", ""),
                        "${ORVD_TOPIC}":             env_dict.get("ORVD_TOPIC", ""),
                        "${DRONEPORT_TOPIC}":        env_dict.get("DRONEPORT_TOPIC", ""),
                        "${SITL_TOPIC}":             env_dict.get("SITL_TOPIC", ""),
                        "${SITL_COMMANDS_TOPIC}":    env_dict.get("SITL_COMMANDS_TOPIC", "sitl.commands"),
                        "${SITL_TELEMETRY_REQUEST_TOPIC}": env_dict.get(
                            "SITL_TELEMETRY_REQUEST_TOPIC", "sitl.telemetry.request"),
                        "${SITL_VERIFIER_HOME_TOPIC}": env_dict.get(
                            "SITL_VERIFIER_HOME_TOPIC", "sitl-drone-home"),
                    }
                    sp = env_dict["SECURITY_POLICIES"]
                    for placeholder, value in _subs.items():
                        sp = sp.replace(placeholder, value)
                    try:
                        policies = json.loads(sp)
                        policies += [
                            {"sender": "e2e_test_host", "topic": f"{_A}.autopilot",        "action": "get_state"},
                            {"sender": "e2e_test_host", "topic": f"{_A}.security_monitor", "action": "*"},
                        ]
                        env_dict["SECURITY_POLICIES"] = json.dumps(policies)
                    except (json.JSONDecodeError, ValueError):
                        env_dict["SECURITY_POLICIES"] = sp

            # GCS drone_manager & mission_converter need to reach the Agrodron
            # SecurityMonitor at the monorepo topic scheme (components.Agrodron.*)
            # rather than the GCS default "v1.Agrodron.Agrodron001.*".
            if sys_name.lower() == "gcs" and original_name in (
                "drone_manager", "mission_converter", "orchestrator",
            ):
                # Override compose-defaults `v1.Agrodron.Agrodron001.*`.
                # AgroDron слушает на `components.Agrodron.*`.
                env_dict["AGRODRON_SECURITY_MONITOR_TOPIC"] = "components.Agrodron.security_monitor"
                env_dict["AGRODRON_MISSION_HANDLER_TOPIC"] = "components.Agrodron.mission_handler"
                env_dict["AGRODRON_AUTOPILOT_TOPIC"] = "components.Agrodron.autopilot"
                env_dict["AGRODRON_TELEMETRY_TOPIC"] = "components.Agrodron.telemetry"

            if sys_name.lower() == "sitl-module":
                env_dict["BROKER_BACKEND"] = os.getenv("E2E_BROKER", "kafka")
                env_dict["BROKER_TYPE"] = os.getenv("E2E_BROKER", "kafka")
                env_dict["KAFKA_SERVERS"] = "kafka:29092"
                env_dict["KAFKA_BOOTSTRAP_SERVERS"] = "kafka:29092"
                env_dict["MQTT_BROKER"] = "mosquitto"
                env_dict["MQTT_PORT"] = "1883"
                env_dict["REDIS_URL"] = "redis://redis:6379"
                # Монорепный broker/ (монтируется в /app/broker) использует
                # SASL_PLAINTEXT когда заданы BROKER_USER/PASSWORD.
                env_dict["BROKER_USER"] = "${ADMIN_USER:-admin}"
                env_dict["BROKER_PASSWORD"] = "${ADMIN_PASSWORD:-admin_secret_123}"

            # Agregator (Go): Kafka + при MQTT дублирование operator-трафика в Mosquitto.
            if sys_name.lower() == "agregator" and os.getenv("E2E_BROKER") == "mqtt":
                if original_name == "aggregator":
                    env_dict["OPERATOR_TRANSPORT"] = "both"
                    env_dict["MQTT_BROKER"] = "mosquitto:1883"
                    env_dict["MQTT_USERNAME"] = env_dict.get(
                        "BROKER_USER", "${ADMIN_USER:-admin}"
                    )
                    env_dict["MQTT_PASSWORD"] = env_dict.get(
                        "BROKER_PASSWORD", "${ADMIN_PASSWORD:-admin_secret_123}"
                    )

            # Insurer (Java/Spring): MQTT профиль, его MqttConfig читает
            # MQTT_SERVER / MQTT_USERNAME / MQTT_PASSWORD.
            # NB: на момент написания insurer/.../MqttConfig.java эти переменные
            # ещё не читает (только MQTT_SERVER, причём дефолт tcp://localhost:1883).
            # До фикса используется alt_insurer как drop-in замена в e2e-mqtt.
            if sys_name.lower() == "insurer" and os.getenv("E2E_BROKER") == "mqtt":
                env_dict["MQTT_SERVER"] = "tcp://mosquitto:1883"
                env_dict["MQTT_USERNAME"] = env_dict.get(
                    "BROKER_USER", "${ADMIN_USER:-admin}"
                )
                env_dict["MQTT_PASSWORD"] = env_dict.get(
                    "BROKER_PASSWORD", "${ADMIN_PASSWORD:-admin_secret_123}"
                )

            # alt_insurer выступает как drop-in замена insurer на время, пока
            # Java-insurer не починит MQTT auth. Слушает на systems.insurer
            # (через INSURER_GATEWAY_TOPIC), чтобы Operator/тесты не правились.
            if sys_name.lower() == "alt_insurer" and os.getenv("E2E_BROKER") == "mqtt":
                if original_name == "insurer_gateway":
                    env_dict["SYSTEM_ID"] = "insurer"
                    env_dict["INSURER_GATEWAY_TOPIC"] = "systems.insurer"

            if sys_name.lower() == "drones":
                # Apстрим (extract/deliverydron-module-2) параметризовал пути.
                env_dict["DELIVERYDRON_ROOT"] = "systems/drones"
                env_dict["TOPIC_SCHEME"] = "components"
                env_dict["SYSTEM_NAME"] = "deliverydron"
                env_dict["INSTANCE_ID"] = "delivery_001"
                # bus/src/factory.go поддерживает kafka/mqtt через BROKER_TYPE.
                env_dict["BROKER_TYPE"] = os.getenv("E2E_BROKER", "kafka")
                env_dict["KAFKA_BOOTSTRAP_SERVERS"] = "kafka:29092"
                env_dict["MQTT_BROKER"] = "mosquitto"
                env_dict["MQTT_PORT"] = "1883"
                build = svc.get("build")
                if isinstance(build, dict):
                    build_args = build.setdefault("args", {})
                    if isinstance(build_args, dict):
                        build_args["DELIVERYDRON_ROOT"] = "systems/drones"
            # Переписываем hostname'ы внутрисистемных сервисов в env значениях.
            # Например DATABASE_URL: ...@postgres:5432... → ...@agregator_postgres:5432...
            _NON_HOST_KEYS = {
                "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB",
                "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE",
                "MONGO_INITDB_ROOT_USERNAME", "MONGO_INITDB_ROOT_PASSWORD",
                "BROKER_USER", "BROKER_PASSWORD",
                "ADMIN_USER", "ADMIN_PASSWORD",
            }
            for env_key, env_val in env_dict.items():
                if not isinstance(env_val, str):
                    continue
                if env_key in _NON_HOST_KEYS:
                    continue
                for orig_svc, prefixed_svc in svc_name_map.items():
                    if orig_svc in _GLOBAL_SERVICES or orig_svc == original_name:
                        continue
                    # Replace plain service names only for host-like keys
                    # (e.g. POSTGRES_HOST=postgres). Avoid touching credentials/usernames.
                    if env_key_looks_like_hostname(env_key) and env_val == orig_svc:
                        env_val = prefixed_svc
                        continue
                    # Replace hostname in DSN URL authority: user:pass@hostname:PORT
                    env_val = re.sub(
                        rf'(?<=@){re.escape(orig_svc)}(?=:\d)',
                        prefixed_svc,
                        env_val,
                    )
                    # Replace hostname in URL with scheme: proto://hostname[:PORT][/...]
                    env_val = re.sub(
                        rf'(?<=://){re.escape(orig_svc)}(?=:\d|/|$)',
                        prefixed_svc,
                        env_val,
                    )
                env_dict[env_key] = env_val
            svc["environment"] = env_dict

            ensure_common_network(svc)

            # depends_on -> переименовываем внутрисистемные зависимости с префиксом,
            # глобальные (kafka, mosquitto, redis) оставляем как есть.
            dep = svc.get("depends_on", {})
            if isinstance(dep, list):
                dep = {name: {"condition": "service_started"} for name in dep}
            elif not isinstance(dep, dict):
                dep = {}

            prefixed_dep: Dict[str, Any] = {}
            for dep_name, dep_cfg in dep.items():
                if dep_name in _GLOBAL_SERVICES:
                    prefixed_dep[dep_name] = dep_cfg
                else:
                    # зависимость на сервис той же системы → добавляем lowercase префикс
                    prefixed_dep[f"{sys_name.lower()}_{dep_name}"] = dep_cfg
            dep = prefixed_dep

            dep["kafka"] = {"condition": "service_healthy", "required": False}
            dep["mosquitto"] = {"condition": "service_healthy", "required": False}
            svc["depends_on"] = dep

            if svc_name in merged_services:
                raise RuntimeError(
                    f"Service name collision after normalization: {svc_name} "
                    f"(system={sys_name}, original={original_name})"
                )
            merged_services[svc_name] = svc

    validate_ports(merged_services)

    merged: Dict[str, Any] = {
        "name": "drones",
        "services": merged_services,
        "networks": {
            "drones_net": {
                "driver": "bridge",
                "name": "${DOCKER_NETWORK:-drones_net}",
            }
        },
    }
    if merged_volumes:
        merged["volumes"] = merged_volumes

    merged_env = parse_env_file(broker_env_path)

    compose_out = output_dir / "docker-compose.yml"
    env_out = output_dir / ".env"
    with open(compose_out, "w") as f:
        f.write(
            "# AUTO-GENERATED by scripts/prepare_multi.py\n"
            "# Do not edit manually.\n"
            f"# Systems: {', '.join(systems)}\n"
        )
        yaml.dump(merged, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    write_env_file(env_out, merged_env)

    print(f"Generated: {compose_out}")
    print(f"Generated: {env_out}")
    print(f"Systems: {', '.join(systems)}")
    print("Kafka/MQTT services included once from docker/docker-compose.yml")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare one compose for multiple systems")
    parser.add_argument(
        "--systems",
        nargs="+",
        required=True,
        help="Список систем: drone_port gcs (или systems/drone_port ...)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output directory relative to repo root. Default: .generated/multi",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        args = parse_args()
        prepare_multi(args.systems, args.output)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
