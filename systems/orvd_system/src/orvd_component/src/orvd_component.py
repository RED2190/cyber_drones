"""
OrvdComponent — центральный компонент ОрВД БАС.

- регистрация БАС
- регистрация миссий
- проверка маршрута
- авторизация миссии
- разрешение вылета
- отзыв разрешения
- телеметрия
- проверка запретных зон
- история событий
"""

from typing import Dict, Any, List
from datetime import datetime

from sdk.base_component import BaseComponent
from broker.system_bus import SystemBus

from systems.orvd_system.src.orvd_component.topics import ExternalTopics

class OrvdComponent(BaseComponent):

    def __init__(
        self,
        component_id: str,
        name: str,
        bus: SystemBus,
        topic: str = "components.orvd_component",
    ):
        self.name = name

        # === состояние системы ===
        self._drones: Dict[str, Dict] = {}
        self._missions: Dict[str, Dict] = {}
        self._authorized: set = set()
        self._active_flights: Dict[str, str] = {}
        self._telemetry: Dict[str, Dict] = {}
        self._history: List[Dict] = []

        # зоны
        self._no_fly_zones: Dict[str, Dict] = {}

        super().__init__(
            component_id=component_id,
            component_type="orvd_component",
            topic=topic,
            bus=bus,
        )

        print(f"OrvdComponent '{name}' initialized")

    # ==========================================================
    # REGISTRATION
    # ==========================================================

    def _register_handlers(self):
        self.register_handler("register_drone", self._handle_register_drone)
        self.register_handler("register_mission", self._handle_register_mission)
        self.register_handler("authorize_mission", self._handle_authorize_mission)
        self.register_handler("request_takeoff", self._handle_request_takeoff)
        self.register_handler("revoke_takeoff", self._handle_revoke_takeoff)
        self.register_handler("send_telemetry", self._handle_send_telemetry)
        self.register_handler("request_telemetry", self._handle_request_telemetry)
        self.register_handler("get_history", self._handle_get_history)

        # зоны
        self.register_handler("add_no_fly_zone", self._handle_add_zone)
        self.register_handler("remove_no_fly_zone", self._handle_remove_zone)

    # ==========================================================
    # UTILS
    # ==========================================================

    def _now(self) -> str:
        return datetime.utcnow().isoformat()

    def _log(self, event: str, **kwargs):
        entry = {
            "event": event,
            "timestamp": self._now(),
            **kwargs
        }
        self._history.append(entry)

    # ==========================================================
    # DRONE REGISTRATION
    # ==========================================================

    def _handle_register_drone(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {})
        drone_id = payload.get("drone_id")

        if not drone_id:
            return {"status": "error", "message": "drone_id required"}

        cert_id = str(payload.get("certificate_id", "")).strip()
        if cert_id:
            v = self.bus.request(
                ExternalTopics.REGULATOR,
                {
                    "action": "verify_drone_cert",
                    "sender": self.component_id,
                    "payload": {"drone_id": drone_id, "certificate_id": cert_id},
                },
                timeout=self.EXTERNAL_REQUEST_TIMEOUT,
            )
            if not v or not v.get("success") or not (v.get("payload") or {}).get("valid"):
                return {"status": "error", "message": "regulator rejected drone certificate"}

        self._drones[drone_id] = payload
        self._log("drone_registered", drone_id=drone_id)

        return {
            "status": "registered",
            "drone_id": drone_id,
            "from": self.component_id,
        }

    # ==========================================================
    # MISSION REGISTRATION
    # ==========================================================

    def _handle_register_mission(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {})
        mission_id = payload.get("mission_id")
        drone_id = payload.get("drone_id")
        route = payload.get("route", [])

        if not mission_id or not drone_id:
            return {"status": "error", "message": "mission_id and drone_id required"}

        if drone_id not in self._drones:
            return {"status": "error", "message": "drone not registered"}

        if self._route_violates_zone(route):
            self._log("mission_rejected", mission_id=mission_id, drone_id=drone_id)
            return {
                "status": "rejected",
                "reason": "route intersects no_fly_zone",
                "from": self.component_id,
            }

        self._missions[mission_id] = payload
        self._log("mission_registered", mission_id=mission_id, drone_id=drone_id)

        return {
            "status": "mission_registered",
            "mission_id": mission_id,
            "from": self.component_id,
        }
    # ==========================================================
    # AUTHORIZE MISSION
    # ==========================================================

    def _handle_authorize_mission(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {})
        mission_id = payload.get("mission_id")

        if mission_id not in self._missions:
            return {"status": "error", "message": "mission not found"}

        self._authorized.add(mission_id)
        self._log("mission_authorized", mission_id=mission_id)

        return {
            "status": "authorized",
            "mission_id": mission_id,
            "from": self.component_id,
        }

    # ==========================================================
    # TAKEOFF REQUEST
    # ==========================================================

    def _handle_request_takeoff(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {})
        mission_id = payload.get("mission_id")

        if not mission_id:
            return {"status": "error", "message": "mission_id required"}

        if mission_id not in self._missions:
            return {"status": "takeoff_denied", "reason": "mission not found"}

        if mission_id not in self._authorized:
            return {"status": "takeoff_denied", "reason": "mission not authorized"}

        mission = self._missions[mission_id]
        drone_id = mission.get("drone_id")

        if not drone_id:
            return {"status": "takeoff_denied", "reason": "drone not assigned"}

        if drone_id not in self._drones:
            return {"status": "takeoff_denied", "reason": "drone not registered"}

        if drone_id in self._active_flights:
            return {"status": "takeoff_denied", "reason": "drone already flying"}

        self._active_flights[drone_id] = mission_id
        self._log("takeoff_authorized", drone_id=drone_id, mission_id=mission_id)

        return {
            "status": "takeoff_authorized",
            "drone_id": drone_id,
            "mission_id": mission_id,
            "from": self.component_id,
        }

    # ==========================================================
    # REVOKE TAKEOFF
    # ==========================================================

    def _handle_revoke_takeoff(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {})
        drone_id = payload.get("drone_id")

        if drone_id not in self._active_flights:
            return {"status": "error", "message": "drone not active"}

        mission_id = self._active_flights.pop(drone_id)
        self._log("takeoff_revoked", drone_id=drone_id, mission_id=mission_id)

        return {
            "status": "landing_required",
            "drone_id": drone_id,
            "from": self.component_id,
        }

    # ==========================================================
    # TELEMETRY
    # ==========================================================

    def _handle_send_telemetry(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {})
        drone_id = payload.get("drone_id")
        coords = payload.get("coords", {})

        if not drone_id:
            return {"status": "error", "message": "drone_id required"}

        self._telemetry[drone_id] = payload

        if self._point_in_no_fly_zone(coords):
            self._log("zone_violation", drone_id=drone_id)
            return {
                "status": "emergency",
                "command": "LAND",
                "reason": "entered no_fly_zone",
                "from": self.component_id,
            }

        return {"status": "telemetry_received", "from": self.component_id}
    
    def _handle_request_telemetry(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {})
        drone_id = payload.get("drone_id")

        if not drone_id:
            return {"status": "error", "message": "drone_id required"}

        # Запрашиваем телеметрию у дрона
        try:
            response = self.bus.request(
                topic=payload.get("drone_topic"),   # например v1.Agrodron.Agrodron001.navigation
                message={
                    "action": "get_nav_state",
                    "sender": self.topic,
                    "payload": {"drone_id": drone_id},
                },
                timeout=5.0,
            )
        except Exception:
            return {"status": "error", "message": "telemetry_timeout"}

        nav_payload = response.get("payload", {})
        coords = {
            "lat": nav_payload.get("lat"),
            "lon": nav_payload.get("lon"),
        }

        self._telemetry[drone_id] = nav_payload

        if self._point_in_no_fly_zone(coords):
            self._log("zone_violation", drone_id=drone_id)

            return {
                "status": "emergency",
                "command": "LAND",
                "reason": "entered no_fly_zone",
                "from": self.component_id,
            }

        return {
            "status": "telemetry_ok",
            "coords": coords,
            "from": self.component_id,
    }

    # ==========================================================
    # NO-FLY ZONES
    # ==========================================================

    def _handle_add_zone(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {})
        zone_id = payload.get("zone_id")

        if not zone_id:
            return {"status": "error", "message": "zone_id required"}

        self._no_fly_zones[zone_id] = payload
        self._log("zone_added", zone_id=zone_id)

        return {"status": "zone_added", "zone_id": zone_id}

    def _handle_remove_zone(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {})
        zone_id = payload.get("zone_id")

        self._no_fly_zones.pop(zone_id, None)
        self._log("zone_removed", zone_id=zone_id)

        return {"status": "zone_removed", "zone_id": zone_id}

    # ==========================================================
    # HELPERS
    # ==========================================================

    def _route_violates_zone(self, route: List[Dict]) -> bool:
        for point in route:
            if self._point_in_no_fly_zone(point):
                return True
        return False

    def _point_in_no_fly_zone(self, coords: Dict[str, Any]) -> bool:
        lat = coords.get("lat")
        lon = coords.get("lon")

        if lat is None or lon is None:
            return False

        for zone in self._no_fly_zones.values():
            if not zone.get("active", True):
                continue

            bounds = zone.get("bounds", {})
            min_lat = bounds.get("min_lat")
            max_lat = bounds.get("max_lat")
            min_lon = bounds.get("min_lon")
            max_lon = bounds.get("max_lon")

            if None in (min_lat, max_lat, min_lon, max_lon):
                continue

            if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                return True

        return False

    # ==========================================================
    # HISTORY
    # ==========================================================

    def _handle_get_history(self, message: Dict[str, Any]) -> Dict[str, Any]:
        return {"history": self._history, "from": self.component_id}