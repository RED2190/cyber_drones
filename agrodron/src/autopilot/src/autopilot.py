from typing import Any, Dict, Optional
import math
import threading
import time
from sdk.base_component import BaseComponent
from broker.system_bus import SystemBus
from components.autopilot import config


class AutopilotComponent(BaseComponent):
    """
    Упрощённая реализация автопилота на базе BaseComponent.

    Реализует только хранение миссии, приём навигации и базовые команды управления
    состоянием (START/PAUSE/RESUME/ABORT/EMERGENCY_STOP/KOVER), а также выдачу
    текущего статуса. Управление моторами и опрыскивателем на уровне этой
    заготовки не выполняется.
    """

    def __init__(
        self,
        component_id: str,
        bus: SystemBus,
        topic: str = "",
    ):
        self._mission: Optional[Dict[str, Any]] = None
        self._state: str = "IDLE"
        self._current_step_index: Optional[int] = None
        self._last_nav_state: Optional[Dict[str, Any]] = None
        self._sprayer_state: str = "OFF"

        # Флаг активного режима «Ковер»: в этом режиме автопилот выполняет
        # посадку до земли, затем переходит в ожидание (PAUSED).
        self._kover_active: bool = False

        self._control_thread: Optional[threading.Thread] = None
        self._control_interval_s: float = config.autopilot_control_interval_s()
        self._nav_poll_interval_s: float = config.autopilot_nav_poll_interval_s()
        self._request_timeout_s: float = config.autopilot_request_timeout_s()
        self._last_nav_poll_ts: float = 0.0

        super().__init__(
            component_id=component_id,
            component_type="autopilot",
            topic=(topic or config.component_topic()),
            bus=bus,
        )

    # ------------------------------------------------------------------ utils

    @staticmethod
    def _is_trusted_sender(message: Dict[str, Any]) -> bool:
        sender = message.get("sender")
        return isinstance(sender, str) and sender.startswith("security_monitor")

    # ------------------------------------------------------------ registration

    def _register_handlers(self) -> None:
        self.register_handler("mission_load", self._handle_mission_load)
        self.register_handler("cmd", self._handle_cmd)
        self.register_handler("get_state", self._handle_get_state)

    # --------------------------------------------------------------- lifecycle

    def start(self) -> None:
        super().start()
        self._control_thread = threading.Thread(
            target=self._control_loop,
            name=f"{self.component_id}_control",
            daemon=True,
        )
        self._control_thread.start()

    def stop(self) -> None:
        super().stop()
        # Ничего дополнительно делать не нужно: _running уже обнулён.

    # ---------------------------------------------------------------- handlers

    def _handle_mission_load(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._is_trusted_sender(message):
            return None

        payload = message.get("payload") or {}
        mission = payload.get("mission")
        if not isinstance(mission, dict):
            return {"ok": False, "error": "invalid_mission"}

        self._mission = mission
        self._current_step_index = 0 if mission.get("steps") else None
        self._state = "MISSION_LOADED"
        self._log_to_journal("AUTOPILOT_MISSION_LOADED", {"mission_id": mission.get("mission_id"), "state": self._state})
        return {"ok": True, "state": self._state}

    def _handle_cmd(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._is_trusted_sender(message):
            return None

        payload = message.get("payload") or {}
        command = str(payload.get("command") or "").upper()
        old_state = self._state

        if command == "START":
            if self._mission is None:
                return {"ok": False, "error": "no_mission"}
            self._state = "EXECUTING"
        elif command == "PAUSE":
            if self._state == "EXECUTING":
                self._state = "PAUSED"
        elif command == "RESUME":
            if self._state == "PAUSED":
                self._state = "EXECUTING"
        elif command == "ABORT":
            self._state = "ABORTED"
        elif command == "RESET":
            self._mission = None
            self._current_step_index = None
            self._state = "IDLE"
        elif command == "EMERGENCY_STOP":
            # Полная остановка автопилота по аварийной команде.
            self._state = "EMERGENCY_STOP"
            self._log_to_journal("AUTOPILOT_EMERGENCY_STOP", {"old_state": old_state})
        elif command == "KOVER":
            # Команда «Ковер»: инициировать посадку до земли.
            # Управляющий цикл будет уменьшать высоту до 0 и после посадки
            # переведёт автопилот в состояние PAUSED (ожидание возобновления).
            self._kover_active = True
            self._log_to_journal("AUTOPILOT_KOVER_ACTIVE", {})
            # Оставляем состояние EXECUTING, чтобы контрольный цикл работал.
            if self._state not in ("EXECUTING", "PAUSED"):
                self._state = "EXECUTING"
        else:
            return {"ok": False, "error": "unknown_command"}

        if old_state != self._state:
            self._log_to_journal("AUTOPILOT_STATE_CHANGE", {"old_state": old_state, "new_state": self._state, "command": command})
        return {"ok": True, "state": self._state}

    def _handle_get_state(self, message: Dict[str, Any]) -> Dict[str, Any]:
        # Запрос состояния может приходить от любых отправителей через монитор.
        steps = self._mission.get("steps") if isinstance(self._mission, dict) else None
        total_steps = len(steps) if isinstance(steps, list) else 0

        return {
            "state": self._state,
            "mission_id": self._mission.get("mission_id") if self._mission else None,
            "current_step_index": self._current_step_index,
            "total_steps": total_steps,
            "sprayer_state": self._sprayer_state,
            "last_nav_state": self._last_nav_state,
        }

    # ------------------------------------------------------------- control loop

    def _control_loop(self) -> None:
        """Простейший управляющий цикл автопилота."""
        while self._running:
            try:
                self._poll_navigation_if_due()
                self._step_control()
            except Exception as exc:  # прототип: только логируем
                print(f"[{self.component_id}] control loop error: {exc}")
            time.sleep(self._control_interval_s)

    def _poll_navigation_if_due(self) -> None:
        now = time.monotonic()
        if (now - self._last_nav_poll_ts) < self._nav_poll_interval_s:
            return
        self._last_nav_poll_ts = now

        message = {
            "action": "proxy_request",
            "sender": self.component_id,
            "payload": {
                "target": {
                    "topic": config.topic_for("navigation"),
                    "action": config.navigation_get_state_action(),
                },
                "data": {},
            },
        }
        response = self.bus.request(
            config.security_monitor_topic(),
            message,
            timeout=self._request_timeout_s,
        )
        if not isinstance(response, dict):
            return

        target_response = response.get("target_response")
        if not isinstance(target_response, dict):
            return

        nav_payload = target_response.get("payload")
        if isinstance(nav_payload, dict):
            self._last_nav_state = nav_payload

    def _step_control(self) -> None:
        if self._last_nav_state is None:
            return

        # Обработка режима «Ковер»: посадка до земли, затем ожидание.
        if self._kover_active:
            try:
                alt = float(self._last_nav_state.get("alt_m"))
                lat = float(self._last_nav_state.get("lat", 0.0))
                lon = float(self._last_nav_state.get("lon", 0.0))
            except (TypeError, ValueError):
                return

            ground_alt = 0.0
            self._send_motors_target(
                vx=0.0, vy=0.0, vz=-1.0,
                alt_m=ground_alt,
                lat=lat, lon=lon,
                heading_deg=self._last_nav_state.get("heading_deg", 0.0),
                drop=False,
            )
            self._send_sprayer(False)

            if abs(alt - ground_alt) <= 0.5:
                # Считаем, что квадрокоптер сел на землю.
                self._kover_active = False
                self._state = "PAUSED"
                self._log_to_journal("AUTOPILOT_KOVER_LANDED", {})
            return

        if self._mission is None:
            return

        if self._state not in ("EXECUTING", "PAUSED"):
            return

        steps = self._mission.get("steps") or []
        if not steps:
            return

        if self._current_step_index is None:
            self._current_step_index = 0

        if self._current_step_index >= len(steps):
            self._state = "COMPLETED"
            self._log_to_journal("AUTOPILOT_MISSION_COMPLETED", {"mission_id": self._mission.get("mission_id")})
            return

        step = steps[self._current_step_index]

        # Навигация
        try:
            lat = float(self._last_nav_state.get("lat"))
            lon = float(self._last_nav_state.get("lon"))
            alt = float(self._last_nav_state.get("alt_m"))
            t_lat = float(step.get("lat"))
            t_lon = float(step.get("lon"))
            t_alt = float(step.get("alt_m"))
        except (TypeError, ValueError):
            return

        d_lat = t_lat - lat
        d_lon = t_lon - lon
        distance_m = math.hypot(d_lat, d_lon) * 111_000.0

        # Порог достижения точки
        reach_threshold_m = 2.0
        if distance_m <= reach_threshold_m:
            if self._current_step_index < len(steps) - 1:
                self._current_step_index += 1
                step = steps[self._current_step_index]
                try:
                    t_lat = float(step.get("lat"))
                    t_lon = float(step.get("lon"))
                    t_alt = float(step.get("alt_m"))
                except (TypeError, ValueError):
                    return
                d_lat = t_lat - lat
                d_lon = t_lon - lon
                distance_m = math.hypot(d_lat, d_lon) * 111_000.0
            else:
                # Последняя точка достигнута
                self._state = "COMPLETED"
                self._log_to_journal("AUTOPILOT_MISSION_COMPLETED", {"mission_id": self._mission.get("mission_id")})
                self._send_motors_target(
                    vx=0.0, vy=0.0, vz=0.0,
                    alt_m=alt,
                    lat=lat, lon=lon,
                    heading_deg=self._last_nav_state.get("heading_deg", 0.0),
                    drop=False,
                )
                self._send_sprayer(False)
                return

        # В состоянии PAUSED отправляем "удержание": нулевая скорость, опрыскиватель выключен.
        if self._state == "PAUSED":
            self._send_motors_target(
                vx=0.0, vy=0.0, vz=0.0,
                alt_m=alt,
                lat=lat, lon=lon,
                heading_deg=self._last_nav_state.get("heading_deg", 0.0),
                drop=False,
            )
            self._send_sprayer(False)
            return

        # EXECUTING: расчёт векторов скорости и направления
        heading_rad = math.atan2(d_lon, d_lat) if (d_lat != 0 or d_lon != 0) else 0.0
        heading_deg = (math.degrees(heading_rad) + 360.0) % 360.0

        speed_mps = float(step.get("speed_mps") or 5.0)
        target_alt = t_alt

        vx, vy, vz = self._compute_velocity_vectors(
            heading_deg=heading_deg,
            ground_speed_mps=speed_mps,
            current_alt=alt,
            target_alt=target_alt,
        )

        spray_flag = bool(step.get("spray"))
        self._send_motors_target(
            vx=vx, vy=vy, vz=vz,
            alt_m=target_alt,
            lat=lat, lon=lon,
            heading_deg=heading_deg,
            drop=spray_flag,
        )
        self._send_sprayer(spray_flag)

    def _compute_velocity_vectors(
        self,
        heading_deg: float,
        ground_speed_mps: float,
        current_alt: float,
        target_alt: float,
        max_climb_rate_mps: float = 3.0,
    ) -> tuple[float, float, float]:
        """
        Вычисляет 3 компоненты вектора скорости (vx, vy, vz) для SITL.
        vx — скорость на восток (м/с), vy — на север (м/с), vz — вертикальная (м/с).
        """
        heading_rad = math.radians(heading_deg)
        vx = ground_speed_mps * math.sin(heading_rad)
        vy = ground_speed_mps * math.cos(heading_rad)
        alt_diff = target_alt - current_alt
        if abs(alt_diff) < 0.2:
            vz = 0.0
        else:
            vz = max(-max_climb_rate_mps, min(max_climb_rate_mps, alt_diff * 2.0))
        return (vx, vy, vz)

    def _send_motors_target(
        self,
        vx: float,
        vy: float,
        vz: float,
        alt_m: float,
        lat: float,
        lon: float,
        heading_deg: float,
        drop: bool = False,
    ) -> None:
        """Отправка команды приводам с векторами скорости для SITL."""
        message = {
            "action": "proxy_publish",
            "sender": self.component_id,
            "payload": {
                "target": {"topic": config.topic_for("motors"), "action": "SET_TARGET"},
                "data": {
                    "vx": vx, "vy": vy, "vz": vz,
                    "alt_m": alt_m,
                    "lat": lat, "lon": lon,
                    "heading_deg": heading_deg,
                    "drop": drop,
                },
            },
        }
        self.bus.publish(config.security_monitor_topic(), message)

    def _send_sprayer(self, spray: bool) -> None:
        """Отправка команды опрыскивателю через монитор безопасности."""
        self._sprayer_state = "ON" if spray else "OFF"
        message = {
            "action": "proxy_publish",
            "sender": self.component_id,
            "payload": {
                "target": {
                    "topic": config.topic_for("sprayer"),
                    "action": "SET_SPRAY",
                },
                "data": {
                    "spray": spray,
                },
            },
        }
        self.bus.publish(config.security_monitor_topic(), message)

    def _log_to_journal(self, event: str, details: Dict[str, Any]) -> None:
        """Отправка события в журнал через монитор безопасности."""
        msg = {
            "action": "proxy_publish",
            "sender": self.component_id,
            "payload": {
                "target": {"topic": config.journal_topic(), "action": "LOG_EVENT"},
                "data": {"event": event, "source": "autopilot", "details": details},
            },
        }
        self.bus.publish(config.security_monitor_topic(), msg)


