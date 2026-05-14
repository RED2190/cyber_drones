import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sdk.base_component import BaseComponent
from broker.system_bus import SystemBus

from systems.agrodron.src.mission_handler import config
from systems.agrodron.src.mission_handler.src.wpl_parser import parse_wpl


class MissionHandlerComponent(BaseComponent):
    """
    Обработчик миссий агродрона.

    На вход поступают **строго файлы WPL** (QGC WPL / ArduPilot Waypoint).
    Другие форматы на вход не принимаются — преобразование в WPL должно
    выполняться до отправки в этот компонент.

    Обработчик:
    - парсит WPL и преобразует в JSON-формат автопилота;
    - валидирует миссию;
    - передаёт её в автопилот через монитор безопасности;
    - пишет ключевые события в журнал.
    """

    def __init__(
        self,
        component_id: str,
        bus: SystemBus,
        topic: str = "",
    ):
        self._last_mission: Optional[Dict[str, Any]] = None
        self._last_error: Optional[str] = None

        super().__init__(
            component_id=component_id,
            component_type="mission_handler",
            topic=(topic or config.component_topic()),
            bus=bus,
        )

    # ------------------------------------------------------------ registration

    def _register_handlers(self) -> None:
        self.register_handler("load_mission", self._handle_load_mission)
        self.register_handler("validate_only", self._handle_validate_only)
        self.register_handler("get_state", self._handle_get_state)

    # ------------------------------------------------------------------ utils

    @staticmethod
    def _is_trusted_sender(message: Dict[str, Any]) -> bool:
        """Принимаем сообщения только от монитора безопасности."""
        sender = message.get("sender")
        return isinstance(sender, str) and sender == config.security_monitor_topic()

    # ---------------------------------------------------------------- handlers

    def _handle_load_mission(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._is_trusted_sender(message):
            return None

        payload = message.get("payload") or {}
        wpl_content = payload.get("wpl_content") if isinstance(payload, dict) else None

        if not wpl_content or not isinstance(wpl_content, str):
            self._last_error = "invalid_input_wpl_required"
            self._log_to_journal(
                event="MISSION_HANDLER_VALIDATION_ERROR",
                details={"error": self._last_error},
            )
            return {"ok": False, "error": self._last_error}

        mission_id = payload.get("mission_id") if isinstance(payload, dict) else None
        mission, parse_error = parse_wpl(wpl_content, mission_id=mission_id)

        if mission is None:
            self._last_error = parse_error or "wpl_parse_failed"
            self._log_to_journal(
                event="MISSION_HANDLER_VALIDATION_ERROR",
                details={"error": self._last_error, "wpl_preview": wpl_content[:200]},
            )
            return {"ok": False, "error": self._last_error}

        ok, error = self._validate_mission(mission)
        if not ok:
            self._last_error = error
            self._log_to_journal(
                event="MISSION_HANDLER_VALIDATION_ERROR",
                details={"error": error, "mission_id": mission.get("mission_id")},
            )
            return {"ok": False, "error": error}

        self._last_mission = mission
        self._last_error = None
        mid = mission.get("mission_id")

        self._log_to_journal(
            event="MISSION_HANDLER_MISSION_RECEIVED",
            details={"mission_id": mid},
        )

        request_message: Dict[str, Any] = {
            "action": "proxy_request",
            "sender": self.topic,
            "payload": {
                "target": {
                    "topic": config.autopilot_topic(),
                    "action": "mission_load",
                },
                "data": {
                    "mission": mission,
                },
            },
        }
        response = self.bus.request(
            topic=config.security_monitor_topic(),
            message=request_message,
            timeout=config.mission_handler_request_timeout_s(),
        )
        if not response:
            error = "autopilot_no_response"
            self._last_error = error
            self._log_to_journal(
                event="MISSION_HANDLER_AUTOPILOT_ERROR",
                details={"error": error, "mission_id": mid},
            )
            return {"ok": False, "error": error}

        ap_resp = response.get("target_response") or response.get("payload") or response
        if not isinstance(ap_resp, dict):
            ap_resp = {}
        if not ap_resp.get("ok", True):
            error = str(ap_resp.get("error") or "autopilot_error")
            self._last_error = error
            self._log_to_journal(
                event="MISSION_HANDLER_AUTOPILOT_ERROR",
                details={"error": error, "mission_id": mid},
            )
            return {"ok": False, "error": error}

        self._log_to_journal(
            event="MISSION_HANDLER_MISSION_SENT_TO_AUTOPILOT",
            details={"mission_id": mid},
        )
        # HOME assignment is managed by DronePort during takeoff flow.
        self._log_to_journal(
            event="MISSION_HANDLER_SITL_HOME_SKIPPED",
            details={
                "mission_id": mid,
                "reason": "home_managed_by_droneport",
            },
        )
        return {"ok": True}

    def _handle_validate_only(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._is_trusted_sender(message):
            return None

        payload = message.get("payload") or {}
        wpl_content = payload.get("wpl_content") if isinstance(payload, dict) else None

        if not wpl_content or not isinstance(wpl_content, str):
            self._last_error = "invalid_input_wpl_required"
            self._log_to_journal(
                event="MISSION_HANDLER_VALIDATION_ERROR",
                details={"error": self._last_error},
            )
            return {"ok": False, "error": self._last_error}

        mission_id = payload.get("mission_id") if isinstance(payload, dict) else None
        mission, parse_error = parse_wpl(wpl_content, mission_id=mission_id)

        if mission is None:
            self._last_error = parse_error or "wpl_parse_failed"
            self._log_to_journal(
                event="MISSION_HANDLER_VALIDATION_ERROR",
                details={"error": self._last_error},
            )
            return {"ok": False, "error": self._last_error}

        ok, error = self._validate_mission(mission)
        if not ok:
            self._last_error = error
            self._log_to_journal(
                event="MISSION_HANDLER_VALIDATION_ERROR",
                details={"error": error},
            )
            return {"ok": False, "error": error}

        self._last_error = None
        return {"ok": True}

    def _handle_get_state(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._is_trusted_sender(message):
            return None

        return {
            "last_mission": self._last_mission,
            "last_error": self._last_error,
        }

    # ------------------------------------------------------------- validations

    def _validate_mission(self, mission: Dict[str, Any]) -> tuple[bool, str]:
        if not isinstance(mission, dict):
            return False, "mission_not_dict"

        mission_id = mission.get("mission_id")
        if not isinstance(mission_id, str) or not mission_id:
            return False, "invalid_mission_id"

        steps = mission.get("steps")
        if not isinstance(steps, list) or not steps:
            return False, "empty_steps"

        for idx, step in enumerate(steps):
            if not isinstance(step, dict):
                return False, f"invalid_step_{idx}"
            for field in ("lat", "lon", "alt_m"):
                if field not in step:
                    return False, f"missing_{field}_in_step_{idx}"

        return True, ""

    # ------------------------------------------------------------ SITL HOME

    def _build_home_message(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Формирует сообщение HOME в формате SITL из первого waypoint."""
        lat = float(step.get("lat") or 0.0)
        lon = float(step.get("lon") or 0.0)
        alt_m = float(step.get("alt_m") or 0.0)
        now = datetime.now(timezone.utc)
        time_str = now.strftime("%H%M%S.000")
        date_str = now.strftime("%d%m%y")
        lat_nmea = f"{int(abs(lat)):02d}{int((abs(lat) % 1) * 60):02d}.{int(round(((abs(lat) % 1) * 60) % 1 * 10000)):04d}"
        lon_nmea = f"{int(abs(lon)):03d}{int((abs(lon) % 1) * 60):02d}.{int(round(((abs(lon) % 1) * 60) % 1 * 10000)):04d}"
        lat_dir = "N" if lat >= 0 else "S"
        lon_dir = "E" if lon >= 0 else "W"
        return {
            "drone_id": config.sitl_drone_id(),
            "msg_id": str(uuid.uuid4()),
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "nmea": {
                "rmc": {
                    "talker_id": "GN",
                    "time": time_str,
                    "status": "A",
                    "latitude": lat_nmea,
                    "lat_dir": lat_dir,
                    "longitude": lon_nmea,
                    "lon_dir": lon_dir,
                    "speed_knots": 0.0,
                    "course_degrees": 0.0,
                    "date": date_str,
                },
                "gga": {
                    "talker_id": "GN",
                    "time": time_str,
                    "latitude": lat_nmea,
                    "lat_dir": lat_dir,
                    "longitude": lon_nmea,
                    "lon_dir": lon_dir,
                    "quality": 1,
                    "satellites": 10,
                    "hdop": 0.8,
                },
            },
            "derived": {
                "lat_decimal": round(lat, 6),
                "lon_decimal": round(lon, 6),
                "altitude_msl": round(alt_m, 2),
                "gps_valid": True,
                "satellites_used": 10,
                "position_accuracy_hdop": 0.8,
            },
        }

    def _send_home_to_sitl(self, mission: Dict[str, Any]) -> None:
        """Отправляет HOME в SITL через proxy_publish."""
        steps = mission.get("steps") if isinstance(mission, dict) else []
        if not steps:
            return
        sitl = config.sitl_topic()
        if not sitl:
            self._log_to_journal(
                "MISSION_HANDLER_SITL_HOME_SKIPPED",
                {"reason": "SITL_TOPIC_empty", "mission_id": mission.get("mission_id") if isinstance(mission, dict) else None},
            )
            return
        home_msg = self._build_home_message(steps[0])
        mid = mission.get("mission_id") if isinstance(mission, dict) else None
        lat = float(steps[0].get("lat") or 0.0)
        lon = float(steps[0].get("lon") or 0.0)
        alt_m = float(steps[0].get("alt_m") or 0.0)
        self._log_to_journal(
            "MISSION_HANDLER_SITL_HOME_SENDING",
            {
                "mission_id": mid,
                "sitl_topic": sitl,
                "drone_id": config.sitl_drone_id(),
                "home_lat": lat,
                "home_lon": lon,
                "home_alt_m": alt_m,
                "phase": "before_proxy_publish",
            },
        )
        message = {
            "action": "proxy_publish",
            "sender": self.topic,
            "payload": {
                "target": {"topic": sitl, "action": "set_home"},
                "data": home_msg,
            },
        }
        ok = self.bus.publish(config.security_monitor_topic(), message)
        if ok:
            self._log_to_journal(
                "MISSION_HANDLER_SITL_HOME_SENT",
                {
                    "mission_id": mid,
                    "sitl_topic": sitl,
                    "drone_id": config.sitl_drone_id(),
                    "home_lat": lat,
                    "home_lon": lon,
                    "home_alt_m": alt_m,
                    "phase": "publish_ok",
                },
            )
        else:
            self._log_to_journal(
                "MISSION_HANDLER_SITL_HOME_SEND_FAILED",
                {
                    "mission_id": mid,
                    "sitl_topic": sitl,
                    "drone_id": config.sitl_drone_id(),
                    "phase": "publish_failed",
                },
            )

        # SITL-module verifier подписан на sitl-drone-home (RAW JSON), а не на SITL_TOPIC — без этого Redis не заполняется.
        self._send_verifier_home_raw(lat, lon, alt_m, mid)

    def _send_verifier_home_raw(
        self,
        home_lat: float,
        home_lon: float,
        home_alt: float,
        mission_id: Optional[str],
    ) -> None:
        vtopic = config.sitl_verifier_home_topic()
        if not vtopic:
            return
        raw = {
            "drone_id": config.sitl_drone_id(),
            "home_lat": home_lat,
            "home_lon": home_lon,
            "home_alt": home_alt,
        }
        self._log_to_journal(
            "MISSION_HANDLER_SITL_HOME_VERIFIER_SENDING",
            {
                "mission_id": mission_id,
                "verifier_home_topic": vtopic,
                "drone_id": raw["drone_id"],
                "home_lat": home_lat,
                "home_lon": home_lon,
                "home_alt": home_alt,
            },
        )
        msg = {
            "action": "proxy_publish",
            "sender": self.topic,
            "payload": {
                "target": {"topic": vtopic, "action": "__raw__"},
                "data": raw,
            },
        }
        ok = self.bus.publish(config.security_monitor_topic(), msg)
        if ok:
            self._log_to_journal(
                "MISSION_HANDLER_SITL_HOME_VERIFIER_SENT",
                {
                    "mission_id": mission_id,
                    "verifier_home_topic": vtopic,
                    "drone_id": raw["drone_id"],
                    "note": "Формат sitl-drone-home.json для SITL verifier → controller → Redis.",
                },
            )
        else:
            self._log_to_journal(
                "MISSION_HANDLER_SITL_HOME_VERIFIER_FAILED",
                {"mission_id": mission_id, "verifier_home_topic": vtopic},
            )

    # -------------------------------------------------------------- journal log

    def _log_to_journal(self, event: str, details: Dict[str, Any]) -> None:
        message = {
            "action": "proxy_publish",
            "sender": self.topic,
            "payload": {
                "target": {
                    "topic": config.journal_topic(),
                    "action": "log_event",
                },
                "data": {
                    "event": event,
                    "source": "mission_handler",
                    "details": details,
                },
            },
        }
        self.bus.publish(config.security_monitor_topic(), message)
