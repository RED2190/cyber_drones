from typing import Any, Dict, Optional
import math
import threading
import time
from sdk.base_component import BaseComponent
from broker.system_bus import SystemBus
from systems.agrodron.src.autopilot import config
from systems.agrodron.scripts.proxy_reply import extract_navigation_nav_state_from_target_response
from systems.agrodron.scripts.proxy_reply import unwrap_proxy_target_response


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
        self._mission_condition = threading.Condition()
        self._state: str = "IDLE"
        self._current_step_index: Optional[int] = None
        self._preflight_passed: bool = False
        self._last_error: Optional[str] = None
        self._last_nav_state: Optional[Dict[str, Any]] = None
        self._sprayer_state: str = "OFF"

        # Флаг активного режима «Ковер»: в этом режиме автопилот выполняет
        # посадку до земли, затем переходит в ожидание (PAUSED).
        self._kover_active: bool = False
        self._landing_active: bool = False
        self._landing_port_confirmed: bool = False
        self._last_landing_port_request_ts: float = 0.0
        self._landing_port_retry_interval_s: float = 2.0

        self._control_thread: Optional[threading.Thread] = None
        self._control_interval_s: float = config.autopilot_control_interval_s()
        self._nav_poll_interval_s: float = config.autopilot_nav_poll_interval_s()
        self._request_timeout_s: float = config.autopilot_request_timeout_s()
        self._start_mission_wait_s: float = config.autopilot_start_mission_wait_s()
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
        return isinstance(sender, str) and sender == config.security_monitor_topic()

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

        with self._mission_condition:
            self._mission = mission
            self._current_step_index = 0 if mission.get("steps") else None
            self._state = "MISSION_LOADED"
            self._mission_condition.notify_all()
        self._log_to_journal("AUTOPILOT_MISSION_LOADED", {"mission_id": mission.get("mission_id"), "state": self._state})
        return {"ok": True, "state": self._state}

    def _handle_cmd(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._is_trusted_sender(message):
            return None

        payload = message.get("payload") or {}
        command = str(payload.get("command") or "").upper()
        old_state = self._state

        if command == "START":
            if self._mission is None and not self._wait_for_mission_before_start():
                return {
                    "ok": False,
                    "error": "no_mission",
                    "waited_s": self._start_mission_wait_s,
                }
            if self._state not in ("MISSION_LOADED", "IDLE"):
                return {"ok": False, "error": "invalid_state_for_start", "state": self._state}

            # Возвращаем промежуточный статус. НУС поймет, что мы готовимся.
            self._state = "PRE_FLIGHT"
            self._log_to_journal("AUTOPILOT_START_ACCEPTED", {"mission_id": self._mission.get("mission_id"), "state": self._state})
            return {"ok": True, "state": "PRE_FLIGHT"}
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

    def _wait_for_mission_before_start(self) -> bool:
        """START может прийти чуть раньше mission_load; ждём короткое окно."""
        timeout_s = self._start_mission_wait_s
        if timeout_s <= 0:
            return self._mission is not None

        deadline = time.monotonic() + timeout_s
        with self._mission_condition:
            while self._mission is None:
                remaining_s = deadline - time.monotonic()
                if remaining_s <= 0:
                    return False
                self._mission_condition.wait(timeout=remaining_s)
            return True

    def _handle_get_state(self, message: Dict[str, Any]) -> Dict[str, Any]:
        # Запрос состояния может приходить от любых отправителей через монитор.
        steps = self._mission.get("steps") if isinstance(self._mission, dict) else None
        total_steps = len(steps) if isinstance(steps, list) else 0

        return {
            "state": self._state,
            "last_error": self._last_error,
            "mission_id": self._mission.get("mission_id") if self._mission else None,
            "current_step_index": self._current_step_index,
            "total_steps": total_steps,
            "sprayer_state": self._sprayer_state,
            "last_nav_state": self._last_nav_state,
        }

    # ------------------------------------------------------------- control loop

    def _control_loop(self) -> None:
        """Простейший управляющий цикл автопилота."""
        # Даём шине и основному потоку потребителя немного времени на прогрев
        time.sleep(2.0)
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
            "sender": self.topic,
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
        target_response = unwrap_proxy_target_response(response)
        nav_state = extract_navigation_nav_state_from_target_response(target_response)
        if isinstance(nav_state, dict):
            self._last_nav_state = nav_state

    def _step_control(self) -> None:
        if self._last_nav_state is None:
            return

        if self._state == "PRE_FLIGHT":
            mission_id = self._mission.get("mission_id", "") if self._mission else "unknown"
            self._last_error = None # Сбрасываем старую ошибку при новой попытке
            
            # 1. Проверка ОРВД
            if not self._request_departure_orvd(mission_id):
                self._state = "ABORTED"
                self._last_error = "orvd_denied"
                return

            # 2. Проверка Дронопорта
            if not self._request_takeoff_droneport(mission_id):
                self._state = "ABORTED"
                self._last_error = "droneport_denied"
                return

            # Всё отлично, взлетаем!
            self._state = "EXECUTING"
            self._log_to_journal("AUTOPILOT_PREFLIGHT_PASSED", {"mission_id": mission_id})
            return

        if self._landing_active:
            self._handle_mission_landing()
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

        # Расчёт 3D-расстояния до целевой точки
        d_lat = t_lat - lat
        d_lon = t_lon - lon
        d_alt = t_alt - alt
        # Конвертация градусов в метры (приблизительно)
        horizontal_distance_m = math.hypot(d_lat, d_lon) * 111_000.0
        distance_m = math.sqrt(horizontal_distance_m**2 + d_alt**2)

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
                mid = self._mission.get("mission_id")
                self._send_sprayer(False)
                self._start_mission_landing(mid)
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
            "sender": self.topic,
            "payload": {
                "target": {"topic": config.topic_for("motors"), "action": "set_target"},
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
            "sender": self.topic,
            "payload": {
                "target": {
                    "topic": config.topic_for("sprayer"),
                    "action": "set_spray",
                },
                "data": {
                    "spray": spray,
                },
            },
        }
        self.bus.publish(config.security_monitor_topic(), message)

    def _log_to_journal(self, event: str, details: Dict[str, Any]) -> None:
        msg = {
            "action": "proxy_publish",
            "sender": self.topic,
            "payload": {
                "target": {"topic": config.journal_topic(), "action": "log_event"},
                "data": {"event": event, "source": "autopilot", "details": details},
            },
        }
        self.bus.publish(config.security_monitor_topic(), msg)

    # ------------------------------------------------ external system requests

    @staticmethod
    def _unwrap_proxy_target_response(response: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        target_response = unwrap_proxy_target_response(response)
        if target_response is None:
            return response if isinstance(response, dict) else None
        target_payload = target_response.get("payload")
        if isinstance(target_payload, dict):
            return target_payload
        return target_response

    def _proxy_request_external(self, topic: str, action: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not topic:
            return None
        message = {
            "action": "proxy_request",
            "sender": self.topic,
            "payload": {
                "target": {"topic": topic, "action": action},
                "data": data,
            },
        }
        response = self.bus.request(
            config.security_monitor_topic(),
            message,
            timeout=self._request_timeout_s,
        )
        if not isinstance(response, dict):
            return None
        return self._unwrap_proxy_target_response(response)

    def _request_departure_orvd(self, mission_id: str) -> bool:
        topic = config.orvd_topic()
        if not topic:
            return True
        if config.orvd_mock_success():
            self._log_to_journal(
                "ORVD_TAKEOFF_APPROVED",
                {"mission_id": mission_id, "stub": True, "reason": "AUTOPILOT_ORVD_MOCK_SUCCESS"},
            )
            return True
        from datetime import datetime, timezone
        payload = {
            "drone_id": config.orvd_drone_id(),
            "mission_id": mission_id,
            "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        resp = self._proxy_request_external(topic, "request_takeoff", payload)
        if resp and resp.get("status") == "takeoff_authorized":
            self._log_to_journal("ORVD_TAKEOFF_APPROVED", {"mission_id": mission_id})
            return True
        self._log_to_journal("ORVD_TAKEOFF_DENIED", {"mission_id": mission_id, "response": resp})
        return False

    def _droneport_battery_pct(self, *, default: float) -> float:
        """Процент заряда из последней навигации или default."""
        nav = self._last_nav_state or {}
        for key in ("battery_pct", "battery", "bat_pct"):
            if key in nav:
                try:
                    return float(nav[key])
                except (TypeError, ValueError):
                    break
        return default

    @staticmethod
    def _unwrap_droneport_response(raw: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Снимает обёртки proxy_request (в т.ч. вложенный target_response/payload)."""
        cur: Any = raw
        for _ in range(6):
            if not isinstance(cur, dict):
                return None
            if cur.get("error") is not None or "port_id" in cur:
                return cur
            pl = cur.get("payload")
            if isinstance(pl, dict) and (pl.get("error") is not None or "port_id" in pl):
                return pl
            nxt = unwrap_proxy_target_response(cur)
            if isinstance(nxt, dict) and nxt is not cur:
                cur = nxt
                continue
            nxt2 = cur.get("target_response")
            if isinstance(nxt2, dict):
                cur = nxt2
                continue
            if isinstance(pl, dict):
                tr = pl.get("target_response")
                if isinstance(tr, dict):
                    cur = tr
                    continue
            break
        return cur if isinstance(cur, dict) else None

    def _droneport_takeoff_ok(self, resp: Optional[Dict[str, Any]]) -> bool:
        """Ответ DronePort `request_takeoff`: успех без `error`, с данными о порте/батарее."""
        body = self._unwrap_droneport_response(resp)
        if not isinstance(body, dict) or body.get("error"):
            return False
        return "port_id" in body or "battery" in body

    def _droneport_landing_ok(self, resp: Optional[Dict[str, Any]]) -> bool:
        """Ответ DronePort `request_landing`: назначен порт."""
        body = self._unwrap_droneport_response(resp)
        if not isinstance(body, dict) or body.get("error"):
            return False
        return bool(body.get("port_id"))

    def _request_takeoff_droneport(self, mission_id: str) -> bool:
        """Соответствует DronePort `request_takeoff` (выезд с порта / взлёт)."""
        topic = config.droneport_topic()
        if not topic:
            return True
        if config.droneport_mock_success():
            self._log_to_journal(
                "DRONEPORT_TAKEOFF_APPROVED",
                {"mission_id": mission_id, "stub": True, "reason": "AUTOPILOT_DRONEPORT_MOCK_SUCCESS"},
            )
            return True
        resp = self._proxy_request_external(
            topic,
            "request_takeoff",
            {
                "drone_id": config.orvd_drone_id(),
            },
        )
        if self._droneport_takeoff_ok(resp):
            self._log_to_journal("DRONEPORT_TAKEOFF_APPROVED", {"mission_id": mission_id})
            return True
        self._log_to_journal("DRONEPORT_TAKEOFF_DENIED", {"mission_id": mission_id, "response": resp})
        return False

    def _request_landing_droneport(self) -> bool:
        topic = config.droneport_topic()
        if not topic:
            return True
        if config.droneport_mock_success():
            return True
        resp = self._proxy_request_external(
            topic,
            "request_landing",
            {
                "drone_id": config.orvd_drone_id(),
                "model": config.droneport_drone_model(),
                "battery": self._droneport_battery_pct(
                    default=config.droneport_landing_battery_default(),
                ),
            },
        )
        ok = self._droneport_landing_ok(resp)
        if ok:
            self._log_to_journal("DRONEPORT_LANDING_APPROVED", {"response": resp})
        else:
            self._log_to_journal("DRONEPORT_LANDING_DENIED", {"response": resp})
        return ok

    def _notify_nus(self, event: str, details: Dict[str, Any]) -> None:
        topic = config.nus_topic()
        if not topic:
            return
        message = {
            "action": "proxy_publish",
            "sender": self.topic,
            "payload": {
                "target": {"topic": topic, "action": "mission_status"},
                "data": {"event": event, **details},
            },
        }
        self.bus.publish(config.security_monitor_topic(), message)

    def _start_mission_landing(self, mission_id: Optional[str]) -> None:
        self._landing_active = True
        self._landing_port_confirmed = False
        self._last_landing_port_request_ts = 0.0
        self._state = "LANDING"
        self._landing_port_confirmed = self._request_landing_droneport()
        self._last_landing_port_request_ts = time.monotonic()
        if not self._landing_port_confirmed:
            self._notify_nus(
                "mission_waiting_landing_port",
                {
                    "mission_id": mission_id,
                },
            )
        self._log_to_journal("AUTOPILOT_LANDING_STARTED", {"mission_id": mission_id})

    def _handle_mission_landing(self) -> None:
        if not self._last_nav_state:
            return

        try:
            alt = float(self._last_nav_state.get("alt_m"))
            lat = float(self._last_nav_state.get("lat", 0.0))
            lon = float(self._last_nav_state.get("lon", 0.0))
        except (TypeError, ValueError):
            return

        if not self._landing_port_confirmed:
            # Backward-compatible landing flow: if landing mode was entered
            # externally (without _start_mission_landing), do not block descent.
            if self._last_landing_port_request_ts <= 0.0:
                self._landing_port_confirmed = True

        if not self._landing_port_confirmed:
            now = time.monotonic()
            if (now - self._last_landing_port_request_ts) >= self._landing_port_retry_interval_s:
                self._landing_port_confirmed = self._request_landing_droneport()
                self._last_landing_port_request_ts = now

            # Keep position while waiting DronePort landing approval.
            self._send_motors_target(
                vx=0.0, vy=0.0, vz=0.0,
                alt_m=alt, lat=lat, lon=lon,
                heading_deg=self._last_nav_state.get("heading_deg", 0.0),
                drop=False,
            )
            return

        heading = self._last_nav_state.get("heading_deg", 0.0)
        if alt <= 0.5:
            self._send_motors_target(
                vx=0.0, vy=0.0, vz=0.0,
                alt_m=0.0, lat=lat, lon=lon,
                heading_deg=heading,
                drop=False,
            )
            self._self_diagnostics()
            self._request_charging_droneport()

            mid = self._mission.get("mission_id") if self._mission else None
            drone_id = config.orvd_drone_id()
            self._notify_nus("mission_completed", {"mission_id": mid, "drone_id": drone_id})
            self._log_to_journal("AUTOPILOT_MISSION_COMPLETED", {"mission_id": mid})
            self._log_to_journal("AUTOPILOT_READY_FOR_NEW_MISSION", {"mission_id": mid})

            self._landing_active = False
            self._mission = None
            self._current_step_index = None
            self._state = "IDLE"
            return

        self._send_motors_target(
            vx=0.0, vy=0.0, vz=-1.0,
            alt_m=0.0, lat=lat, lon=lon,
            heading_deg=heading,
            drop=False,
        )

    def _self_diagnostics(self) -> bool:
        """Заглушка самодиагностики. TODO: реализовать реальные проверки."""
        return True

    def _request_charging_droneport(self) -> None:
        """Соответствует DronePort `request_charging` (запрос зарядки на порту)."""
        topic = config.droneport_topic()
        if not topic:
            return
        if config.droneport_mock_success():
            return
        resp = self._proxy_request_external(
            topic,
            "request_charging",
            {
                "drone_id": config.orvd_drone_id(),
                "battery": self._droneport_battery_pct(
                    default=config.droneport_charging_battery_default(),
                ),
            },
        )
        if isinstance(resp, dict) and not resp.get("error"):
            self._log_to_journal("DRONEPORT_CHARGING_REQUESTED", {"response": resp})
        else:
            self._log_to_journal("DRONEPORT_CHARGING_REQUEST_FAILED", {"response": resp})
