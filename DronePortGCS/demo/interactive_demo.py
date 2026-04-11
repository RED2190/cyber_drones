from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from broker.src.bus_factory import create_system_bus
from systems.drone_port.src.drone_manager.topics import (
    ComponentTopics as DronePortDroneManagerTopics,
    DroneManagerActions as DronePortDroneManagerActions,
)
from systems.drone_port.src.drone_registry.topics import (
    ComponentTopics as DroneRegistryTopics,
    DroneRegistryActions,
)
from systems.drone_port.src.orchestrator.topics import (
    ComponentTopics as DronePortOrchestratorTopics,
    OrchestratorActions as DronePortOrchestratorActions,
)
from systems.drone_port.src.port_manager.topics import (
    ComponentTopics as PortManagerTopics,
    PortManagerActions,
)
from systems.gcs.src.mission_store.topics import (
    ComponentTopics as MissionStoreTopics,
    MissionStoreActions,
)
from systems.gcs.src.drone_store.topics import (
    ComponentTopics as DroneStoreTopics,
    DroneStoreActions,
)
from systems.gcs.src.orchestrator.topics import (
    ComponentTopics as GCSOrchestratorTopics,
    OrchestratorActions as GCSOrchestratorActions,
)
from systems.gcs.src.drone_manager.topics import ComponentTopics as GCSDroneManagerTopics
from systems.gcs.topics import DroneActions, DroneTopics


ROOT = Path(__file__).resolve().parents[1]
DOCKER_DIR = ROOT / "docker"
DOCKER_ENV = DOCKER_DIR / ".env"
DOCKER_ENV_EXAMPLE = DOCKER_DIR / "example.env"
GCS_DIR = ROOT / "systems" / "gcs"
DRONE_PORT_DIR = ROOT / "systems" / "drone_port"
GCS_GENERATED_DIR = GCS_DIR / ".generated"
DRONE_PORT_GENERATED_DIR = DRONE_PORT_DIR / ".generated"
CYBER_DRONS_DIR = ROOT / "external" / "cyber_drons"
AGRODRON_DIR = CYBER_DRONS_DIR / "agrodron"
AGRODRON_GENERATED_DIR = AGRODRON_DIR / ".generated"
SITL_MODULE_DIR = ROOT / "external" / "sitl_module"
SITL_COMPOSE_FILE = SITL_MODULE_DIR / "docker-compose.yaml"
SITL_OBSERVED_TOPICS = [
    "sitl",
    "sitl-drone-home",
    "sitl.commands",
    "sitl.telemetry.request",
    "sitl.telemetry.response",
    "sitl.verified-home",
    "sitl.verified-commands",
]
AGRODRON_COMPONENT_SERVICES = [
    "security_monitor",
    "journal",
    "navigation",
    "autopilot",
    "limiter",
    "emergensy",
    "mission_handler",
    "motors",
    "sprayer",
    "telemetry",
]


def parse_env_file(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        return env

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def write_env_file(path: Path, env: Dict[str, str]) -> None:
    lines = [f"{key}={value}" for key, value in env.items()]
    path.write_text("\n".join(lines) + "\n")


def default_task_waypoints() -> List[Dict[str, float]]:
    return [
        {"lat": 55.751244, "lon": 37.618423, "alt_m": 0.0},
        {"lat": 55.750900, "lon": 37.620200, "alt_m": 120.0},
        {"lat": 55.752400, "lon": 37.622000, "alt_m": 120.0},
    ]


class DockerInteractiveDemo:
    def __init__(self, client_id: str = "web_demo_client"):
        self.client_id = client_id
        self.bus = None
        self.observed_drone_messages: List[Dict[str, Any]] = []
        self.observed_sitl_messages: List[Dict[str, Any]] = []

    def _run(
        self,
        command: List[str],
        cwd: Path | None = None,
        timeout: int = 1800,
        env: Optional[Dict[str, str]] = None,
    ) -> str:
        result = subprocess.run(
            command,
            cwd=str(cwd or ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
            env=env,
        )
        return (result.stdout or "") + (result.stderr or "")

    def _run_stream(
        self,
        command: List[str],
        cwd: Path | None = None,
        timeout: int = 1800,
        on_output: Optional[Callable[[str], None]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> str:
        process = subprocess.Popen(
            command,
            cwd=str(cwd or ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )

        lines: List[str] = []

        try:
            assert process.stdout is not None
            started_at = time.time()
            for line in process.stdout:
                lines.append(line)
                if on_output:
                    on_output(line)
                if time.time() - started_at > timeout:
                    process.kill()
                    raise subprocess.TimeoutExpired(command, timeout)

            return_code = process.wait(timeout=max(1, timeout - int(time.time() - started_at)))
        except Exception:
            process.kill()
            process.wait()
            raise

        output = "".join(lines)
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command, output=output)
        return output

    def _compose(
        self,
        compose_file: Path,
        env_file: Path,
        args: List[str],
        cwd: Path | None = None,
        env: Optional[Dict[str, str]] = None,
    ) -> str:
        command = [
            "docker",
            "compose",
            "-f",
            str(compose_file),
            "--env-file",
            str(env_file),
            *args,
        ]
        return self._run(command, cwd=cwd or ROOT, env=env)

    def _compose_stream(
        self,
        compose_file: Path,
        env_file: Path,
        args: List[str],
        cwd: Path | None = None,
        on_output: Optional[Callable[[str], None]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> str:
        command = [
            "docker",
            "compose",
            "-f",
            str(compose_file),
            "--env-file",
            str(env_file),
            *args,
        ]
        return self._run_stream(command, cwd=cwd or ROOT, on_output=on_output, env=env)

    def _docker(self, args: List[str], cwd: Path | None = None) -> str:
        return self._run(["docker", *args], cwd=cwd or ROOT)

    def _docker_stream(
        self,
        args: List[str],
        cwd: Path | None = None,
        on_output: Optional[Callable[[str], None]] = None,
    ) -> str:
        return self._run_stream(["docker", *args], cwd=cwd or ROOT, on_output=on_output)

    def ensure_root_env(self) -> str:
        if DOCKER_ENV.exists():
            return f"Using existing env file: {DOCKER_ENV}"

        shutil.copyfile(DOCKER_ENV_EXAMPLE, DOCKER_ENV)
        return f"Created env file from template: {DOCKER_ENV}"

    def ensure_cyber_drons_available(self) -> None:
        if AGRODRON_DIR.exists():
            return
        raise FileNotFoundError(
            "Submodule external/cyber_drons is missing. Run: git submodule update --init --recursive"
        )

    def sync_cyber_drons_env(self) -> str:
        self.ensure_cyber_drons_available()
        root_env = parse_env_file(DOCKER_ENV)
        generated_env_path = AGRODRON_GENERATED_DIR / ".env"
        generated_env = parse_env_file(generated_env_path)
        synced_keys = [
            "BROKER_TYPE",
            "ADMIN_USER",
            "ADMIN_PASSWORD",
            "DOCKER_NETWORK",
            "MQTT_PORT",
            "KAFKA_PORT",
            "KAFKA_INTERNAL_PORT",
        ]

        for key in synced_keys:
            if key in root_env:
                generated_env[key] = root_env[key]

        generated_env["BROKER_USER"] = root_env.get("ADMIN_USER", "admin")
        generated_env["BROKER_PASSWORD"] = root_env.get("ADMIN_PASSWORD", "admin_secret_123")
        generated_env["MQTT_BROKER"] = "mosquitto"
        generated_env["KAFKA_BOOTSTRAP_SERVERS"] = "kafka:29092"
        write_env_file(generated_env_path, generated_env)
        return f"Synchronized AgroDron broker settings: {generated_env_path}"

    def prepare_cyber_drons(self) -> str:
        self.ensure_root_env()
        self.ensure_cyber_drons_available()
        output = self._run(
            ["python3", "scripts/prepare_system.py", "agrodron"],
            cwd=CYBER_DRONS_DIR,
        )
        output += "\n" + self.sync_cyber_drons_env()
        return output

    def prepare_cyber_drons_stream(self, on_output: Optional[Callable[[str], None]] = None) -> str:
        self.ensure_root_env()
        self.ensure_cyber_drons_available()
        output = self._run_stream(
            ["python3", "scripts/prepare_system.py", "agrodron"],
            cwd=CYBER_DRONS_DIR,
            on_output=on_output,
        )
        sync_message = self.sync_cyber_drons_env()
        if on_output:
            on_output(f"{sync_message}\n")
        return output + "\n" + sync_message

    def prepare_systems(self) -> str:
        self.ensure_root_env()
        output = [self._run(["python3", "scripts/prepare_system.py", "systems/gcs"])]
        output.append(self._run(["python3", "scripts/prepare_system.py", "systems/drone_port"]))
        output.append(self.prepare_cyber_drons())
        return "\n".join(output)

    def prepare_systems_stream(self, on_output: Optional[Callable[[str], None]] = None) -> str:
        self.ensure_root_env()
        output = [self._run_stream(["python3", "scripts/prepare_system.py", "systems/gcs"], on_output=on_output)]
        output.append(
            self._run_stream(["python3", "scripts/prepare_system.py", "systems/drone_port"], on_output=on_output)
        )
        output.append(self.prepare_cyber_drons_stream(on_output=on_output))
        return "\n".join(output)

    def broker_up(self) -> str:
        self.ensure_root_env()
        env = parse_env_file(DOCKER_ENV)
        profile = env.get("BROKER_TYPE", "mqtt")
        return self._compose(
            DOCKER_DIR / "docker-compose.yml",
            DOCKER_ENV,
            ["--profile", profile, "up", "-d"],
        )

    def broker_up_stream(self, on_output: Optional[Callable[[str], None]] = None) -> str:
        self.ensure_root_env()
        env = parse_env_file(DOCKER_ENV)
        profile = env.get("BROKER_TYPE", "mqtt")
        return self._compose_stream(
            DOCKER_DIR / "docker-compose.yml",
            DOCKER_ENV,
            ["--profile", profile, "up", "-d"],
            on_output=on_output,
        )

    def broker_down(self) -> str:
        output = []
        for profile in ("kafka", "mqtt"):
            try:
                output.append(
                    self._compose(
                        DOCKER_DIR / "docker-compose.yml",
                        DOCKER_ENV,
                        ["--profile", profile, "down"],
                    )
                )
            except subprocess.CalledProcessError as exc:
                output.append((exc.stdout or "") + (exc.stderr or ""))
        return "\n".join(output)

    def _sitl_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        env.update(parse_env_file(DOCKER_ENV))
        agrodron_env = parse_env_file(AGRODRON_GENERATED_DIR / ".env")
        env["DOCKER_NETWORK"] = env.get("DOCKER_NETWORK", "drones_net")
        env["BROKER_BACKEND"] = "mqtt"
        env["MQTT_HOST"] = "mosquitto"
        env["MQTT_PORT"] = env.get("MQTT_PORT", "1883")
        env["MQTT_USERNAME"] = env.get("ADMIN_USER", "admin")
        env["MQTT_PASSWORD"] = env.get("ADMIN_PASSWORD", "admin_secret_123")
        env["MQTT_QOS"] = "1"
        env["INPUT_TOPICS"] = ",".join(
            [
                agrodron_env.get("SITL_COMMANDS_TOPIC", "sitl.commands"),
                agrodron_env.get("SITL_HOME_TOPIC", "sitl-drone-home"),
            ]
        )
        env["COMMAND_TOPIC"] = agrodron_env.get("SITL_COMMANDS_TOPIC", "sitl.commands")
        env["HOME_TOPIC"] = agrodron_env.get("SITL_HOME_TOPIC", "sitl-drone-home")
        env["POSITION_REQUEST_TOPIC"] = agrodron_env.get(
            "SITL_TELEMETRY_REQUEST_TOPIC",
            "sitl.telemetry.request",
        )
        env["POSITION_RESPONSE_TOPIC"] = "sitl.telemetry.response"
        return env

    def sitl_up(self) -> str:
        self.ensure_root_env()
        return self._compose(
            SITL_COMPOSE_FILE,
            DOCKER_ENV,
            ["up", "-d", "--build"],
            cwd=SITL_MODULE_DIR,
            env=self._sitl_env(),
        )

    def sitl_up_stream(self, on_output: Optional[Callable[[str], None]] = None) -> str:
        self.ensure_root_env()
        return self._compose_stream(
            SITL_COMPOSE_FILE,
            DOCKER_ENV,
            ["up", "-d", "--build"],
            cwd=SITL_MODULE_DIR,
            on_output=on_output,
            env=self._sitl_env(),
        )

    def sitl_down(self) -> str:
        try:
            return self._compose(
                SITL_COMPOSE_FILE,
                DOCKER_ENV,
                ["down", "--remove-orphans"],
                cwd=SITL_MODULE_DIR,
                env=self._sitl_env(),
            )
        except subprocess.CalledProcessError as exc:
            return (exc.stdout or "") + (exc.stderr or "")

    def gcs_up(self) -> str:
        env = parse_env_file(GCS_GENERATED_DIR / ".env")
        profile = env.get("BROKER_TYPE", "mqtt")
        return self._compose(
            GCS_GENERATED_DIR / "docker-compose.yml",
            GCS_GENERATED_DIR / ".env",
            [
                "--profile",
                profile,
                "up",
                "-d",
                "--build",
                "--no-deps",
                "redis",
                "mission_store",
                "drone_store",
                "mission_converter",
                "orchestrator",
                "path_planner",
                "drone_manager",
            ],
        )

    def gcs_up_stream(self, on_output: Optional[Callable[[str], None]] = None) -> str:
        env = parse_env_file(GCS_GENERATED_DIR / ".env")
        profile = env.get("BROKER_TYPE", "mqtt")
        return self._compose_stream(
            GCS_GENERATED_DIR / "docker-compose.yml",
            GCS_GENERATED_DIR / ".env",
            [
                "--profile",
                profile,
                "up",
                "-d",
                "--build",
                "--no-deps",
                "redis",
                "mission_store",
                "drone_store",
                "mission_converter",
                "orchestrator",
                "path_planner",
                "drone_manager",
            ],
            on_output=on_output,
        )

    def gcs_down(self) -> str:
        output = []
        for profile in ("kafka", "mqtt"):
            try:
                output.append(
                    self._compose(
                        GCS_GENERATED_DIR / "docker-compose.yml",
                        GCS_GENERATED_DIR / ".env",
                        ["--profile", profile, "rm", "-sf", "redis", "mission_store", "drone_store", "mission_converter", "orchestrator", "path_planner", "drone_manager"],
                    )
                )
            except subprocess.CalledProcessError as exc:
                output.append((exc.stdout or "") + (exc.stderr or ""))
        return "\n".join(output)

    def drone_port_up(self) -> str:
        env = parse_env_file(DRONE_PORT_GENERATED_DIR / ".env")
        profile = env.get("BROKER_TYPE", "mqtt")
        return self._compose(
            DRONE_PORT_GENERATED_DIR / "docker-compose.yml",
            DRONE_PORT_GENERATED_DIR / ".env",
            [
                "--profile",
                profile,
                "up",
                "-d",
                "--build",
                "--no-deps",
                "redis",
                "state_store",
                "port_manager",
                "drone_registry",
                "charging_manager",
                "drone_manager",
                "orchestrator",
            ],
        )

    def drone_port_up_stream(self, on_output: Optional[Callable[[str], None]] = None) -> str:
        """Запуск DronePort (без брокера и его зависимостей)"""
        env = parse_env_file(DRONE_PORT_GENERATED_DIR / ".env")
        profile = env.get("BROKER_TYPE", "mqtt")
        
        compose_file = DRONE_PORT_GENERATED_DIR / "docker-compose.yml"
        env_file = DRONE_PORT_GENERATED_DIR / ".env"
        
        if not compose_file.exists():
            raise FileNotFoundError(f"Docker compose file not found: {compose_file}")
        
        # 🔥 Очистка старых контейнеров
        if on_output:
            on_output("[drone_port] Cleaning up existing DronePort containers...\n")
        
        try:
            self._compose_stream(
                compose_file, env_file, ["down", "--remove-orphans"],
                on_output=on_output
            )
        except Exception as e:
            if on_output:
                on_output(f"[drone_port] Warning during down: {e}\n")
        
        # 🔥 Запуск с --no-deps чтобы НЕ запускать зависимости (mosquitto!)
        if on_output:
            on_output("[drone_port] Starting DronePort services (--no-deps to skip broker)...\n")
        
        return self._compose_stream(
            compose_file,
            env_file,
            [
                "--profile", profile,
                "up", "-d",
                "--build",
                "--force-recreate",
                "--remove-orphans",
                "--no-deps",  # 🔥 КЛЮЧЕВОЙ ФЛАГ: не запускать зависимости!
                "redis",
                "state_store",
                "port_manager",
                "drone_registry",
                "charging_manager",
                "drone_manager",
                "orchestrator",
            ],
            on_output=on_output,
        )

    def drone_port_down(self) -> str:
        output = []
        for profile in ("kafka", "mqtt"):
            try:
                output.append(
                    self._compose(
                        DRONE_PORT_GENERATED_DIR / "docker-compose.yml",
                        DRONE_PORT_GENERATED_DIR / ".env",
                        ["--profile", profile, "rm", "-sf", "redis", "state_store", "port_manager", "drone_registry", "charging_manager", "drone_manager", "orchestrator"],
                    )
                )
            except subprocess.CalledProcessError as exc:
                output.append((exc.stdout or "") + (exc.stderr or ""))
        return "\n".join(output)

    def cyber_drons_up(self) -> str:
        env = parse_env_file(AGRODRON_GENERATED_DIR / ".env")
        profile = env.get("BROKER_TYPE", "mqtt")
        return self._compose(
            AGRODRON_GENERATED_DIR / "docker-compose.yml",
            AGRODRON_GENERATED_DIR / ".env",
            [
                "--profile",
                profile,
                "up",
                "-d",
                "--build",
                "--no-deps",
                *AGRODRON_COMPONENT_SERVICES,
            ],
            cwd=CYBER_DRONS_DIR,
        )

    def cyber_drons_up_stream(self, on_output: Optional[Callable[[str], None]] = None) -> str:
        env = parse_env_file(AGRODRON_GENERATED_DIR / ".env")
        profile = env.get("BROKER_TYPE", "mqtt")
        compose_file = AGRODRON_GENERATED_DIR / "docker-compose.yml"
        env_file = AGRODRON_GENERATED_DIR / ".env"

        if not compose_file.exists():
            raise FileNotFoundError(f"Docker compose file not found: {compose_file}")

        if on_output:
            on_output("[cyber_drons] Cleaning up existing AgroDron containers...\n")

        try:
            self._compose_stream(
                compose_file,
                env_file,
                ["down", "--remove-orphans"],
                cwd=CYBER_DRONS_DIR,
                on_output=on_output,
            )
        except Exception as exc:
            if on_output:
                on_output(f"[cyber_drons] Warning during down: {exc}\n")

        if on_output:
            on_output("[cyber_drons] Starting AgroDron services (--no-deps to reuse broker)...\n")

        return self._compose_stream(
            compose_file,
            env_file,
            [
                "--profile",
                profile,
                "up",
                "-d",
                "--build",
                "--force-recreate",
                "--remove-orphans",
                "--no-deps",
                *AGRODRON_COMPONENT_SERVICES,
            ],
            cwd=CYBER_DRONS_DIR,
            on_output=on_output,
        )

    def cyber_drons_down(self) -> str:
        output = []
        for profile in ("kafka", "mqtt"):
            try:
                output.append(
                    self._compose(
                        AGRODRON_GENERATED_DIR / "docker-compose.yml",
                        AGRODRON_GENERATED_DIR / ".env",
                        ["--profile", profile, "rm", "-sf", *AGRODRON_COMPONENT_SERVICES],
                        cwd=CYBER_DRONS_DIR,
                    )
                )
            except subprocess.CalledProcessError as exc:
                output.append((exc.stdout or "") + (exc.stderr or ""))
        return "\n".join(output)

    def up_all(self) -> str:
        output = [
            self.prepare_systems(),
            self.broker_up(),
            self.sitl_up(),
            self.gcs_up(),
            self.drone_port_up(),
            self.cyber_drons_up(),
        ]
        self.wait_for_broker()
        self.connect_bus()
        self.wait_until_ready()
        return "\n".join(output)

    def up_all_stream(self, on_output: Optional[Callable[[str], None]] = None) -> str:
        output: List[str] = []

        def emit(message: str) -> None:
            if on_output:
                if message.endswith("\n"):
                    on_output(message)
                else:
                    on_output(f"{message}\n")

        emit("==> Preparing generated compose files")
        output.append(self.prepare_systems_stream(on_output=on_output))
        emit("==> Starting broker")
        output.append(self.broker_up_stream(on_output=on_output))
        emit("==> Starting SITL")
        output.append(self.sitl_up_stream(on_output=on_output))
        emit("==> Starting GCS")
        output.append(self.gcs_up_stream(on_output=on_output))
        emit("==> Starting DronePort")
        output.append(self.drone_port_up_stream(on_output=on_output))
        emit("==> Starting AgroDron")
        output.append(self.cyber_drons_up_stream(on_output=on_output))
        emit("==> Waiting for broker socket")
        emit(self.wait_for_broker())
        emit("==> Connecting demo bus")
        emit(self.connect_bus())
        emit("==> Waiting until core components respond to ping")
        emit(self.wait_until_ready())
        return "\n".join(output)

    def down_all(self) -> str:
        output = [
            self.disconnect_bus(),
            self.cyber_drons_down(),
            self.drone_port_down(),
            self.gcs_down(),
            self.sitl_down(),
            self.broker_down(),
        ]
        return "\n".join(part for part in output if part)

    def gcs_interactive_up(self) -> str:
        output = [
            self.prepare_systems(),
            self.broker_up(),
            self.gcs_up(),
        ]
        self.wait_for_broker()
        self.connect_bus()
        self.wait_until_gcs_ready()
        return "\n".join(output)

    def gcs_interactive_up_stream(self, on_output: Optional[Callable[[str], None]] = None) -> str:
        output: List[str] = []

        def emit(message: str) -> None:
            if on_output:
                if message.endswith("\n"):
                    on_output(message)
                else:
                    on_output(f"{message}\n")

        emit("==> Preparing generated compose files")
        output.append(self.prepare_systems_stream(on_output=on_output))
        emit("==> Starting broker")
        output.append(self.broker_up_stream(on_output=on_output))
        emit("==> Starting GCS")
        output.append(self.gcs_up_stream(on_output=on_output))
        emit("==> Waiting for broker socket")
        emit(self.wait_for_broker())
        emit("==> Connecting demo bus")
        emit(self.connect_bus())
        emit("==> Waiting until GCS components respond to ping")
        emit(self.wait_until_gcs_ready())
        return "\n".join(output)

    def gcs_interactive_down(self) -> str:
        output = [self.disconnect_bus(), self.gcs_down(), self.broker_down()]
        return "\n".join(part for part in output if part)

    def gcs_ps(self) -> str:
        output = ["[broker]"]
        output.append(self._compose(DOCKER_DIR / "docker-compose.yml", DOCKER_ENV, ["ps"]))
        output.append("[gcs]")
        output.append(self._compose(GCS_GENERATED_DIR / "docker-compose.yml", GCS_GENERATED_DIR / ".env", ["ps"]))
        return "\n".join(output)

    def ps(self) -> str:
        output = ["[broker]"]
        output.append(self._compose(DOCKER_DIR / "docker-compose.yml", DOCKER_ENV, ["ps"]))
        output.append("[sitl]")
        output.append(self._compose(SITL_COMPOSE_FILE, DOCKER_ENV, ["ps"], cwd=SITL_MODULE_DIR, env=self._sitl_env()))
        output.append("[gcs]")
        output.append(self._compose(GCS_GENERATED_DIR / "docker-compose.yml", GCS_GENERATED_DIR / ".env", ["ps"]))
        output.append("[drone_port]")
        output.append(self._compose(DRONE_PORT_GENERATED_DIR / "docker-compose.yml", DRONE_PORT_GENERATED_DIR / ".env", ["ps"]))
        output.append("[cyber_drons]")
        output.append(
            self._compose(
                AGRODRON_GENERATED_DIR / "docker-compose.yml",
                AGRODRON_GENERATED_DIR / ".env",
                ["ps"],
                cwd=CYBER_DRONS_DIR,
            )
        )
        return "\n".join(output)

    def drone_port_health(self) -> Dict[str, Any]:
        raw = self._compose(
            DRONE_PORT_GENERATED_DIR / "docker-compose.yml",
            DRONE_PORT_GENERATED_DIR / ".env",
            ["ps", "--format", "json"],
        )
        raw_text = (raw or "").strip()
        if not raw_text:
            services = []
        else:
            try:
                parsed = json.loads(raw_text)
                services = parsed if isinstance(parsed, list) else [parsed]
            except json.JSONDecodeError:
                services = [
                    json.loads(line)
                    for line in raw_text.splitlines()
                    if line.strip()
                ]

        normalized_services = []
        for service in services:
            state = str(service.get("State") or "unknown").lower()
            health = str(service.get("Health") or "").lower()
            normalized_services.append(
                {
                    "name": service.get("Service") or service.get("Name") or "unknown",
                    "state": state,
                    "health": health or "n/a",
                }
            )

        if not normalized_services:
            return {
                "status": "down",
                "summary": "Контейнеры DronePort не запущены.",
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "services": [],
                "total": 0,
                "healthy": 0,
            }

        healthy_count = 0
        degraded_found = False

        for service in normalized_services:
            state = service["state"]
            health = service["health"]
            is_running = state == "running"
            is_healthy = health in {"healthy", "n/a"}

            if is_running and is_healthy:
                healthy_count += 1
            else:
                degraded_found = True

        total = len(normalized_services)
        if healthy_count == total:
            status = "healthy"
            summary = f"DronePort работает штатно: {healthy_count} из {total} сервисов доступны."
        elif healthy_count == 0:
            status = "down"
            summary = "DronePort недоступен: ни один сервис не находится в healthy/running."
        else:
            status = "degraded" if degraded_found else "healthy"
            summary = f"DronePort работает с деградацией: {healthy_count} из {total} сервисов доступны."

        return {
            "status": status,
            "summary": summary,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "services": normalized_services,
            "total": total,
            "healthy": healthy_count,
        }

    def logs(self, stack: str, service: Optional[str] = None, tail: int = 100) -> str:
        if stack == "broker":
            compose_file = DOCKER_DIR / "docker-compose.yml"
            env_file = DOCKER_ENV
            cwd = ROOT
        elif stack == "gcs":
            compose_file = GCS_GENERATED_DIR / "docker-compose.yml"
            env_file = GCS_GENERATED_DIR / ".env"
            cwd = ROOT
        elif stack == "drone_port":
            compose_file = DRONE_PORT_GENERATED_DIR / "docker-compose.yml"
            env_file = DRONE_PORT_GENERATED_DIR / ".env"
            cwd = ROOT
        elif stack == "cyber_drons":
            compose_file = AGRODRON_GENERATED_DIR / "docker-compose.yml"
            env_file = AGRODRON_GENERATED_DIR / ".env"
            cwd = CYBER_DRONS_DIR
        else:
            raise ValueError("stack must be one of: broker, gcs, drone_port, cyber_drons")

        args = ["logs", "--tail", str(tail)]
        if service:
            args.append(service)
        return self._compose(compose_file, env_file, args, cwd=cwd)

    def _client_env(self) -> Dict[str, str]:
        env = parse_env_file(DOCKER_ENV)
        broker_type = env.get("BROKER_TYPE", "mqtt").lower()

        client_env = dict(os.environ)
        client_env["BROKER_TYPE"] = broker_type
        client_env["BROKER_USER"] = env.get("ADMIN_USER", "admin")
        client_env["BROKER_PASSWORD"] = env.get("ADMIN_PASSWORD", "admin_secret_123")
        client_env["BROKER_HOST"] = "localhost"
        client_env["TOPIC_VERSION"] = env.get("TOPIC_VERSION", "v1")

        if broker_type == "kafka":
            kafka_port = env.get("KAFKA_PORT", "9092")
            client_env["KAFKA_PORT"] = kafka_port
            client_env["KAFKA_BOOTSTRAP_SERVERS"] = f"localhost:{kafka_port}"
        else:
            mqtt_port = env.get("MQTT_PORT", "1883")
            client_env["MQTT_BROKER"] = "localhost"
            client_env["MQTT_PORT"] = mqtt_port

        return client_env

    def wait_for_broker(self, timeout: int = 60) -> str:
        env = parse_env_file(DOCKER_ENV)
        broker_type = env.get("BROKER_TYPE", "mqtt").lower()
        port = int(env.get("KAFKA_PORT", "9092") if broker_type == "kafka" else env.get("MQTT_PORT", "1883"))

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with socket.create_connection(("localhost", port), timeout=2):
                    return f"Broker is available on localhost:{port}"
            except OSError:
                time.sleep(2)

        raise TimeoutError(f"Broker did not become available on localhost:{port} within {timeout} seconds")

    def connect_bus(self) -> str:
        if self.bus is not None:
            return "SystemBus is already connected"

        os.environ.update(self._client_env())
        self.bus = create_system_bus(client_id=self.client_id)
        self.bus.start()
        for topic in DroneTopics.all():
            self.bus.subscribe(topic, self._capture_drone_message)
        for topic in SITL_OBSERVED_TOPICS:
            self.bus.subscribe(topic, lambda message, observed_topic=topic: self._capture_sitl_message(observed_topic, message))
        time.sleep(2)
        return "SystemBus connected and observers subscribed"

    def disconnect_bus(self) -> str:
        if self.bus is None:
            return "SystemBus is already disconnected"

        self.bus.stop()
        self.bus = None
        return "SystemBus disconnected"

    def _capture_drone_message(self, message: Dict[str, Any]) -> None:
        self.observed_drone_messages.append(message)

    def _capture_sitl_message(self, topic: str, message: Dict[str, Any]) -> None:
        self.observed_sitl_messages.append(
            {
                "topic": topic,
                "received_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "message": message,
            }
        )

    def wait_until_ready(self, timeout: int = 120) -> str:
        if self.bus is None:
            self.connect_bus()

        probes = [
            DronePortDroneManagerTopics.DRONE_MANAGER,
            DroneRegistryTopics.DRONE_REGISTRY,
            PortManagerTopics.PORT_MANAGER,
            DronePortOrchestratorTopics.ORCHESTRATOR,
            GCSOrchestratorTopics.GCS_ORCHESTRATOR,
            MissionStoreTopics.GCS_MISSION_STORE,
        ]

        deadline = time.time() + timeout
        ready_topics: set[str] = set()

        while time.time() < deadline:
            for topic in probes:
                if topic in ready_topics:
                    continue
                response = self.bus.request(
                    topic,
                    {"action": "ping", "sender": self.client_id, "payload": {}},
                    timeout=5.0,
                )
                if response and response.get("success"):
                    ready_topics.add(topic)

            if len(ready_topics) == len(probes):
                return "All key components responded to ping"

            time.sleep(2)

        missing = sorted(set(probes) - ready_topics)
        raise TimeoutError(f"Components did not become ready in time: {missing}")

    def wait_until_gcs_ready(self, timeout: int = 120) -> str:
        if self.bus is None:
            self.connect_bus()

        probes = [
            GCSOrchestratorTopics.GCS_ORCHESTRATOR,
            MissionStoreTopics.GCS_MISSION_STORE,
        ]

        deadline = time.time() + timeout
        ready_topics: set[str] = set()

        while time.time() < deadline:
            for topic in probes:
                if topic in ready_topics:
                    continue
                response = self.bus.request(
                    topic,
                    {"action": "ping", "sender": self.client_id, "payload": {}},
                    timeout=5.0,
                )
                if response and response.get("success"):
                    ready_topics.add(topic)

            if len(ready_topics) == len(probes):
                return "All GCS components responded to ping"

            time.sleep(2)

        missing = sorted(set(probes) - ready_topics)
        raise TimeoutError(f"GCS components did not become ready in time: {missing}")

    def request(self, topic: str, action: str, payload: Optional[Dict[str, Any]] = None, timeout: float = 15.0) -> Optional[Dict[str, Any]]:
        if self.bus is None:
            self.connect_bus()

        return self.bus.request(
            topic,
            {
                "action": action,
                "sender": self.client_id,
                "payload": payload or {},
            },
            timeout=timeout,
        )

    def request_with_sender(
        self,
        topic: str,
        action: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        sender: str,
        timeout: float = 15.0,
    ) -> Optional[Dict[str, Any]]:
        if self.bus is None:
            self.connect_bus()

        return self.bus.request(
            topic,
            {
                "action": action,
                "sender": sender,
                "payload": payload or {},
            },
            timeout=timeout,
        )

    def publish(self, topic: str, action: str, payload: Optional[Dict[str, Any]] = None) -> bool:
        if self.bus is None:
            self.connect_bus()

        return self.bus.publish(
            topic,
            {
                "action": action,
                "sender": self.client_id,
                "payload": payload or {},
            },
        )

    def _request_agrodron_autopilot_command(self, command: str) -> Optional[Dict[str, Any]]:
        return self.request_with_sender(
            DroneTopics.SECURITY_MONITOR,
            DroneActions.PROXY_REQUEST,
            {
                "target": {
                    "topic": DroneTopics.AUTOPILOT,
                    "action": DroneActions.CMD,
                },
                "data": {
                    "command": command,
                },
            },
            sender=GCSDroneManagerTopics.GCS_DRONE,
            timeout=15.0,
        )

    def request_landing(self, drone_id: str, model: str = "DemoCopter-X") -> Optional[Dict[str, Any]]:
        return self._request_agrodron_autopilot_command("KOVER")

    def request_charging(self, drone_id: str, battery: float) -> Dict[str, Any]:
        self.publish(
            DronePortDroneManagerTopics.DRONE_MANAGER,
            DronePortDroneManagerActions.REQUEST_CHARGING,
            {"drone_id": drone_id, "battery": battery},
        )
        return {"published": True, "drone_id": drone_id, "battery": battery}

    def wait_for_drone_ready(self, drone_id: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            response = self.get_drone_registry_record(drone_id)
            payload = (response or {}).get("payload", {})
            if payload.get("status") == "ready":
                return response
            time.sleep(1)
        return None

    def request_takeoff(self, drone_id: str) -> Optional[Dict[str, Any]]:
        return self._request_agrodron_autopilot_command("START")

    def get_ports(self) -> Optional[Dict[str, Any]]:
        return self.request(
            PortManagerTopics.PORT_MANAGER,
            PortManagerActions.GET_PORT_STATUS,
            {},
            timeout=10.0,
        )

    def get_drone_registry_record(self, drone_id: str) -> Optional[Dict[str, Any]]:
        return self.request(
            DroneRegistryTopics.DRONE_REGISTRY,
            DroneRegistryActions.GET_DRONE,
            {"drone_id": drone_id},
            timeout=10.0,
        )

    def get_available_droneport_drones(self) -> Optional[Dict[str, Any]]:
        return self.request(
            DronePortOrchestratorTopics.ORCHESTRATOR,
            DronePortOrchestratorActions.GET_AVAILABLE_DRONES,
            {},
            timeout=10.0,
        )

    def submit_task(self, waypoints: Optional[List[Dict[str, float]]] = None) -> Optional[Dict[str, Any]]:
        return self.request(
            GCSOrchestratorTopics.GCS_ORCHESTRATOR,
            GCSOrchestratorActions.TASK_SUBMIT,
            {"waypoints": waypoints or default_task_waypoints()},
            timeout=20.0,
        )

    def get_mission(self, mission_id: str) -> Optional[Dict[str, Any]]:
        return self.request(
            MissionStoreTopics.GCS_MISSION_STORE,
            MissionStoreActions.GET_MISSION,
            {"mission_id": mission_id},
            timeout=15.0,
        )

    def get_drone_state(self, drone_id: str) -> Optional[Dict[str, Any]]:
        return self.request(
            DroneStoreTopics.GCS_DRONE_STORE,
            DroneStoreActions.GET_DRONE,
            {"drone_id": drone_id},
            timeout=10.0,
        )

    def wait_for_mission_status(self, mission_id: str, expected_status: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            response = self.get_mission(mission_id)
            payload = (response or {}).get("payload", {})
            mission = payload.get("mission") or {}
            if mission.get("status") == expected_status:
                return response
            time.sleep(1)
        return None

    def _require_orchestrator_ack(self, response: Optional[Dict[str, Any]], action_name: str) -> Dict[str, Any]:
        if not response:
            raise TimeoutError(f"{action_name}: no response from GCS orchestrator")

        if response.get("success") is False:
            raise RuntimeError(f"{action_name}: request failed on transport layer")

        payload = response.get("payload")
        if not isinstance(payload, dict):
            raise RuntimeError(f"{action_name}: malformed orchestrator response")

        if payload.get("ok") is not True:
            error = payload.get("error") or "unknown orchestrator error"
            raise RuntimeError(f"{action_name}: {error}")

        return response

    def assign_task(self, mission_id: str, drone_id: str) -> Dict[str, Any]:
        before = len(self.observed_drone_messages)
        assign_response = self.request(
            GCSOrchestratorTopics.GCS_ORCHESTRATOR,
            GCSOrchestratorActions.TASK_ASSIGN,
            {"mission_id": mission_id, "drone_id": drone_id},
            timeout=20.0,
        )
        assign_response = self._require_orchestrator_ack(assign_response, "task.assign")
        time.sleep(3)
        return {
            "orchestrator_response": assign_response,
            "mission": self.get_mission(mission_id),
            "new_drone_messages": self.observed_drone_messages[before:],
        }

    def start_task(self, mission_id: str, drone_id: str) -> Dict[str, Any]:
        before = len(self.observed_drone_messages)
        start_response = self.request(
            GCSOrchestratorTopics.GCS_ORCHESTRATOR,
            GCSOrchestratorActions.TASK_START,
            {"mission_id": mission_id, "drone_id": drone_id},
            timeout=20.0,
        )
        start_response = self._require_orchestrator_ack(start_response, "task.start")
        time.sleep(3)
        return {
            "orchestrator_response": start_response,
            "mission": self.get_mission(mission_id),
            "new_drone_messages": self.observed_drone_messages[before:],
        }

    def snapshot(self, drone_id: str, mission_id: Optional[str] = None) -> Dict[str, Any]:
        snapshot = {
            "ports": self.get_ports(),
            "registry_drone": self.get_drone_registry_record(drone_id),
            "available_drones": self.get_available_droneport_drones(),
            "observed_drone_messages": list(self.observed_drone_messages[-10:]),
            "observed_sitl_messages": list(self.observed_sitl_messages[-10:]),
        }
        if mission_id:
            snapshot["mission"] = self.get_mission(mission_id)
        return snapshot

    def snapshot_json(self, drone_id: str, mission_id: Optional[str] = None) -> str:
        return json.dumps(self.snapshot(drone_id=drone_id, mission_id=mission_id), ensure_ascii=False, indent=2)

    def gcs_snapshot(self, drone_id: str, mission_id: Optional[str] = None) -> Dict[str, Any]:
        snapshot = {
            "observed_drone_messages": list(self.observed_drone_messages[-10:]),
            "observed_sitl_messages": list(self.observed_sitl_messages[-10:]),
        }
        if mission_id:
            snapshot["mission"] = self.get_mission(mission_id)
        if drone_id:
            snapshot["drone_id"] = drone_id
            snapshot["drone"] = self.get_drone_state(drone_id)
        return snapshot
