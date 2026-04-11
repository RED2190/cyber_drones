"""DroneManagerComponent для взаимодействия с дронами"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict

from broker.src.system_bus import SystemBus
from sdk.base_component import BaseComponent
from systems.gcs.topics import DroneActions, DroneTopics
from systems.gcs.src.contracts import DroneStatus, MissionStatus
from systems.gcs.src.drone_manager.topics import ComponentTopics, DroneManagerActions
from systems.gcs.src.mission_store.topics import MissionStoreActions
from systems.gcs.src.drone_store.topics import DroneStoreActions

logger = logging.getLogger(__name__)


class DroneManagerComponent(BaseComponent):
    def __init__(self, component_id: str, bus: SystemBus):
        self._telemetry_poll_interval_s = 0.5
        self._telemetry_pollers: dict[str, tuple[threading.Thread, threading.Event]] = {}
        super().__init__(
            component_id=component_id,
            component_type="gcs_drone_manager",
            topic=ComponentTopics.GCS_DRONE,
            bus=bus,
        )

    def _register_handlers(self):
        self.register_handler(DroneManagerActions.MISSION_UPLOAD, self._handle_mission_upload)
        self.register_handler(DroneManagerActions.MISSION_START, self._handle_mission_start)

    def _proxy_request_drone(
        self,
        target_topic: str,
        target_action: str,
        data: Dict[str, Any],
        correlation_id: str | None = None,
        timeout: float = 10.0,
    ) -> Dict[str, Any] | None:
        message = {
            "action": DroneActions.PROXY_REQUEST,
            "sender": ComponentTopics.GCS_DRONE,
            "payload": {
                "target": {
                    "topic": target_topic,
                    "action": target_action,
                },
                "data": data,
            },
        }
        if correlation_id:
            message["correlation_id"] = correlation_id

        response = self.bus.request(
            DroneTopics.SECURITY_MONITOR,
            message,
            timeout=timeout,
        )
        logger.info(
            "[%s] proxy_request target_topic=%s target_action=%s data=%r response=%r",
            self.component_id,
            target_topic,
            target_action,
            data,
            response,
        )
        if not isinstance(response, dict):
            return None
        return self._unwrap_target_response(response)

    def _unwrap_target_response(self, response: Dict[str, Any] | None) -> Dict[str, Any] | None:
        if not isinstance(response, dict):
            return None

        target_response = response.get("target_response")
        if isinstance(target_response, dict):
            return target_response

        payload = response.get("payload")
        if not isinstance(payload, dict):
            return response

        nested_target_response = payload.get("target_response")
        if isinstance(nested_target_response, dict):
            return nested_target_response

        return response

    def _response_payload(self, response: Dict[str, Any] | None) -> Dict[str, Any] | None:
        response = self._unwrap_target_response(response)
        if not isinstance(response, dict):
            return None
        payload = response.get("payload")
        return payload if isinstance(payload, dict) else response

    def _response_ok(self, response: Dict[str, Any] | None) -> bool:
        payload = self._response_payload(response)
        if not isinstance(payload, dict):
            return False
        if response.get("success") is False:
            return False
        return bool(payload.get("ok"))

    def _handle_mission_upload(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {})
        correlation_id = message.get("correlation_id")
        mission_id = payload.get("mission_id")
        drone_id = payload.get("drone_id")
        wpl = payload.get("wpl")
        logger.info(
            "[%s] mission.upload received mission_id=%s drone_id=%s correlation_id=%s",
            self.component_id,
            mission_id,
            drone_id,
            correlation_id,
        )

        upload_response = self._proxy_request_drone(
            DroneTopics.MISSION_HANDLER,
            DroneActions.LOAD_MISSION,
            {
                "mission_id": mission_id,
                "drone_id": drone_id,
                "wpl_content": wpl,
            },
            correlation_id=correlation_id,
        )
        logger.info("[%s] mission.upload drone response=%r", self.component_id, upload_response)

        mission_update_message = {
            "action": MissionStoreActions.UPDATE_MISSION,
            "sender": self.component_id,
            "payload": {
                "mission_id": mission_id,
                "fields": {
                    "assigned_drone": drone_id,
                    "status": MissionStatus.ASSIGNED,
                },
            },
        }
        if correlation_id:
            mission_update_message["correlation_id"] = correlation_id

        self.bus.publish(
            ComponentTopics.GCS_MISSION_STORE,
            mission_update_message,
        )

        drone_update_message = {
            "action": DroneStoreActions.UPDATE_DRONE,
            "sender": self.component_id,
            "payload": {
                "drone_id": drone_id,
                "status": DroneStatus.RESERVED,
            },
        }
        if correlation_id:
            drone_update_message["correlation_id"] = correlation_id

        self.bus.publish(
            ComponentTopics.GCS_DRONE_STORE,
            drone_update_message,
        )

        return None

    def _normalize_telemetry(self, response: Dict[str, Any] | None) -> Dict[str, Any] | None:
        payload = self._response_payload(response)
        if not isinstance(payload, dict):
            return None

        if isinstance(payload, dict) and isinstance(payload.get("telemetry"), dict):
            return payload["telemetry"]

        navigation = payload.get("navigation")
        if not isinstance(navigation, dict):
            return None

        nav_state = navigation.get("payload") if isinstance(navigation.get("payload"), dict) else None
        if nav_state is None:
            nav_state = navigation.get("nav_state") if isinstance(navigation.get("nav_state"), dict) else navigation

        telemetry: Dict[str, Any] = {}
        if nav_state.get("lat") is not None:
            telemetry["latitude"] = nav_state.get("lat")
        if nav_state.get("lon") is not None:
            telemetry["longitude"] = nav_state.get("lon")
        if nav_state.get("alt_m") is not None:
            telemetry["altitude"] = nav_state.get("alt_m")
        if nav_state.get("battery_pct") is not None:
            telemetry["battery"] = nav_state.get("battery_pct")

        motors = payload.get("motors")
        if isinstance(motors, dict) and motors.get("battery") is not None:
            telemetry["battery"] = motors.get("battery")

        return telemetry or None

    def _save_telemetry(self, telemetry: Dict[str, Any], correlation_id: str | None = None) -> None:
        telemetry_message = {
            "action": DroneStoreActions.SAVE_TELEMETRY,
            "sender": self.component_id,
            "payload": {
                "telemetry": telemetry,
            },
        }
        if correlation_id:
            telemetry_message["correlation_id"] = correlation_id

        self.bus.publish(ComponentTopics.GCS_DRONE_STORE, telemetry_message)

    def _poll_telemetry_loop(self, drone_id: str, stop_event: threading.Event) -> None:
        while not stop_event.wait(self._telemetry_poll_interval_s):
            if not self._running:
                break

            response = self._proxy_request_drone(
                DroneTopics.TELEMETRY,
                DroneActions.TELEMETRY_GET,
                {
                    "drone_id": drone_id,
                },
                timeout=5.0,
            )
            print(f"[{self.component_id}] telemetry poll raw response for {drone_id}: {response!r}")

            telemetry = self._normalize_telemetry(response)
            print(f"[{self.component_id}] telemetry poll parsed telemetry for {drone_id}: {telemetry!r}")
            if telemetry is None:
                continue

            telemetry.setdefault("drone_id", drone_id)
            print(f"[{self.component_id}] telemetry poll saving telemetry for {drone_id}: {telemetry!r}")
            self._save_telemetry(telemetry)

    def _start_telemetry_polling(self, drone_id: str) -> None:
        active = self._telemetry_pollers.get(drone_id)
        if active and active[0].is_alive():
            return

        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._poll_telemetry_loop,
            args=(drone_id, stop_event),
            daemon=True,
            name=f"{self.component_id}-telemetry-{drone_id}",
        )
        self._telemetry_pollers[drone_id] = (thread, stop_event)
        thread.start()

    def stop(self):
        for thread, stop_event in self._telemetry_pollers.values():
            stop_event.set()
            thread.join(timeout=1.0)
        self._telemetry_pollers.clear()
        super().stop()

    def _handle_mission_start(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {})
        correlation_id = message.get("correlation_id")
        mission_id = payload.get("mission_id")
        drone_id = payload.get("drone_id")
        logger.info(
            "[%s] mission.start received mission_id=%s drone_id=%s correlation_id=%s",
            self.component_id,
            mission_id,
            drone_id,
            correlation_id,
        )

        start_response = self._proxy_request_drone(
            DroneTopics.AUTOPILOT,
            DroneActions.CMD,
            {
                "command": "START",
            },
            correlation_id=correlation_id,
        )
        logger.info("[%s] mission.start autopilot response=%r", self.component_id, start_response)
        start_payload = self._response_payload(start_response)
        if not self._response_ok(start_response):
            logger.warning(
                "[%s] mission.start failed mission_id=%s drone_id=%s payload=%r",
                self.component_id,
                mission_id,
                drone_id,
                start_payload,
            )
            return {
                "ok": False,
                "mission_id": mission_id,
                "drone_id": drone_id,
                "error": (start_payload or {}).get("error", "mission_start_failed"),
                "start_response": start_response,
            }

        mission_update_message = {
            "action": MissionStoreActions.UPDATE_MISSION,
            "sender": self.component_id,
            "payload": {
                "mission_id": mission_id,
                "fields": {
                    "status": MissionStatus.RUNNING,
                },
            },
        }
        if correlation_id:
            mission_update_message["correlation_id"] = correlation_id

        self.bus.publish(
            ComponentTopics.GCS_MISSION_STORE,
            mission_update_message,
        )

        drone_update_message = {
            "action": DroneStoreActions.UPDATE_DRONE,
            "sender": self.component_id,
            "payload": {
                "drone_id": drone_id,
                "status": DroneStatus.BUSY,
            },
        }
        if correlation_id:
            drone_update_message["correlation_id"] = correlation_id

        self.bus.publish(
            ComponentTopics.GCS_DRONE_STORE,
            drone_update_message,
        )

        if drone_id:
            self._start_telemetry_polling(drone_id)
            logger.info("[%s] mission.start started telemetry polling drone_id=%s", self.component_id, drone_id)

        return {
            "ok": True,
            "mission_id": mission_id,
            "drone_id": drone_id,
            "start_response": start_response,
        }
