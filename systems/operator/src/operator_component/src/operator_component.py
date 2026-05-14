"""
OperatorComponent -- бизнес-логика оператора.

Управляет реестром дронов, обрабатывает запросы на поиск дронов,
взаимодействует с Insurer, ORVD и Agregator через bus.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

from broker.system_bus import SystemBus
from sdk.base_component import BaseComponent

from systems.operator.src.operator_component.topics import (
    ComponentTopics,
    ExternalTopics,
    OperatorActions,
)

logger = logging.getLogger(__name__)


class OperatorComponent(BaseComponent):

    EXTERNAL_REQUEST_TIMEOUT = 15.0
    AGREGATOR_OFFER_RETRIES = 6
    AGREGATOR_OFFER_RETRY_SLEEP_S = 2.0

    def __init__(
        self,
        component_id: str,
        bus: SystemBus,
        topic: str = ComponentTopics.OPERATOR_COMPONENT,
    ):
        self._drones: Dict[str, Dict[str, Any]] = {}
        super().__init__(
            component_id=component_id,
            component_type="operator",
            topic=topic,
            bus=bus,
        )

    def _register_handlers(self):
        self.register_handler(OperatorActions.REGISTER_DRONE, self._handle_register_drone)
        self.register_handler(OperatorActions.REQUEST_AVAILABLE_DRONES, self._handle_request_available_drones)
        self.register_handler(OperatorActions.SELECT_DRONE_AND_SEND_TO_AGGREGATOR, self._handle_select_drone)
        self.register_handler(OperatorActions.BUY_INSURANCE_POLICY, self._handle_buy_insurance)
        self.register_handler(OperatorActions.REGISTER_DRONE_IN_ORVD, self._handle_register_in_orvd)
        self.register_handler(OperatorActions.SEND_ORDER_TO_NUS, self._handle_send_to_nus)
        self.register_handler(OperatorActions.CREATE_ORDER, self._handle_create_order)
        self.register_handler(OperatorActions.CONFIRM_PRICE, self._handle_confirm_price)

    def _handle_register_drone(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Регистрирует дрон в реестре оператора."""
        payload = message.get("payload", {}) or {}
        drone_id = payload.get("drone_id", "")
        if not drone_id:
            raise ValueError("drone_id is required")

        cert_id = payload.get("certificate_id", "").strip()
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
                raise ValueError("regulator rejected drone certificate")

        self._drones[drone_id] = {
            "drone_id": drone_id,
            "model": payload.get("model", ""),
            "capabilities": payload.get("capabilities", {}),
            "status": "available",
            "operator_id": self.component_id,
        }
        print(f"[{self.component_id}] Drone {drone_id} registered")
        return {"status": "registered", "drone_id": drone_id}

    def _handle_request_available_drones(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Возвращает список доступных дронов, подходящих под критерии заказа."""
        payload = message.get("payload", {}) or {}

        available = [
            d for d in self._drones.values()
            if d["status"] == "available"
        ]

        result_drones = []
        for drone in available:
            result_drones.append({
                "drone_id": drone["drone_id"],
                "model": drone.get("model", ""),
                "operator_id": drone.get("operator_id", self.component_id),
                "price": payload.get("budget", 1000),
            })

        return {"drones": result_drones}

    def _handle_select_drone(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Выбирает дрон и помечает его как занятый."""
        payload = message.get("payload", {}) or {}
        drone_id = payload.get("selected_drone_id", "")
        order_id = payload.get("order_id", "")

        drone = self._drones.get(drone_id)
        if not drone:
            raise ValueError(f"drone {drone_id} not found")
        if drone["status"] != "available":
            raise ValueError(f"drone {drone_id} is not available (status: {drone['status']})")

        drone["status"] = "assigned"
        drone["assigned_order"] = order_id

        return {
            "drone_id": drone_id,
            "order_id": order_id,
            "status": "assigned",
        }

    def _handle_buy_insurance(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Покупает страховой полис у Insurer через bus."""
        payload = message.get("payload", {}) or {}
        drone_id = payload.get("drone_id", "")
        coverage_amount = payload.get("coverage_amount", 0)
        insurance_action = payload.get("insurance_action", "mission_insurance")
        insurer_payload = {
            "order_id": payload.get("order_id", ""),
            "operator_id": self.component_id,
            "drone_id": drone_id,
            "coverage_amount": coverage_amount,
        }
        if isinstance(payload.get("incident"), dict):
            insurer_payload["incident"] = payload["incident"]

        response = self.bus.request(
            ExternalTopics.INSURER,
            {
                "action": insurance_action,
                "sender": self.component_id,
                "payload": insurer_payload,
            },
            timeout=self.EXTERNAL_REQUEST_TIMEOUT,
        )

        if response is None:
            raise TimeoutError("insurer did not respond")

        if response.get("success"):
            if insurance_action == "report_incident":
                return {
                    "status": "incident_processed",
                    "claim": response.get("payload", {}),
                }
            return {
                "status": "insured",
                "policy": response.get("payload", {}),
            }

        raise RuntimeError(f"insurance failed: {response.get('error', 'unknown')}")

    def _handle_register_in_orvd(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Регистрирует дрон в ORVD через bus."""
        payload = message.get("payload", {}) or {}
        drone_id = payload.get("drone_id", "")

        if not drone_id:
            raise ValueError("drone_id is required")

        orvd_payload: Dict[str, Any] = {
            "drone_id": drone_id,
            "model": payload.get("model", ""),
            "operator_id": self.component_id,
        }
        if payload.get("certificate_id"):
            orvd_payload["certificate_id"] = str(payload.get("certificate_id", "")).strip()

        response = self.bus.request(
            ExternalTopics.ORVD,
            {
                "action": "register_drone",
                "sender": self.component_id,
                "payload": orvd_payload,
            },
            timeout=self.EXTERNAL_REQUEST_TIMEOUT,
        )

        if response is None:
            raise TimeoutError("ORVD did not respond")

        if response.get("success"):
            return {
                "status": "registered_in_orvd",
                "drone_id": drone_id,
                "orvd_response": response.get("payload", {}),
            }

        raise RuntimeError(f"ORVD registration failed: {response.get('error', 'unknown')}")

    def _handle_send_to_nus(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Отправляет заказ в НУС (заглушка -- НУС не реализован)."""
        payload = message.get("payload", {}) or {}
        return {
            "status": "sent_to_nus",
            "order_id": payload.get("order_id", ""),
            "note": "NUS integration pending",
        }

    # ---- Agregator integration (Kafka topics) ----

    def _handle_create_order(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Обрабатывает create_order от Агрегатора: подбирает дрон, рассчитывает
        стоимость с учётом миссионной страховки и отправляет price_offer обратно."""
        payload = message.get("payload", {}) or {}
        if isinstance(payload, (str, bytes)):
            payload = json.loads(payload)

        order_id = (
            message.get("correlation_id", "")
            or message.get("request_id", "")
            or payload.get("order_id", "")
        )
        budget = float(payload.get("budget", 0) or 0)

        available = [d for d in self._drones.values() if d["status"] == "available"]
        if not available:
            logger.warning("[%s] create_order: no available drones for order %s",
                           self.component_id, order_id)
            return None

        best = available[0]
        drone_id = best["drone_id"]

        base_price = budget * 0.85 if budget else 1000.0

        insurance_premium = 0.0
        try:
            ins_resp = self.bus.request(
                ExternalTopics.INSURER,
                {
                    "action": "mission_insurance",
                    "sender": self.component_id,
                    "payload": {
                        "order_id": order_id,
                        "operator_id": self.component_id,
                        "drone_id": drone_id,
                        "coverage_amount": budget,
                    },
                },
                timeout=self.EXTERNAL_REQUEST_TIMEOUT,
            )
            if ins_resp and ins_resp.get("success"):
                ins_pl = ins_resp.get("payload") or {}
                insurance_premium = float(ins_pl.get("premium", 0))
                logger.info("[%s] mission insurance premium=%.2f for order %s",
                            self.component_id, insurance_premium, order_id)
        except Exception as exc:
            logger.warning("[%s] insurance request failed for order %s: %s",
                           self.component_id, order_id, exc)

        total_price = base_price + insurance_premium

        offer = {
            "action": "price_offer",
            "sender": self.component_id,
            "correlation_id": order_id,
            "payload": {
                "order_id": order_id,
                "operator_id": self.component_id,
                "operator_name": self.component_id,
                "price": round(total_price, 2),
                "estimated_time_minutes": 30,
                "insurance_coverage": f"mission_{insurance_premium:.0f}",
            },
        }
        for attempt in range(1, self.AGREGATOR_OFFER_RETRIES + 1):
            self.bus.publish(ExternalTopics.AGREGATOR_RESPONSES, offer)
            logger.info(
                "[%s] published price_offer attempt=%s/%s order=%s price=%.2f",
                self.component_id,
                attempt,
                self.AGREGATOR_OFFER_RETRIES,
                order_id,
                total_price,
            )
            if attempt < self.AGREGATOR_OFFER_RETRIES:
                time.sleep(self.AGREGATOR_OFFER_RETRY_SLEEP_S)
        return {"status": "offer_sent", "order_id": order_id, "price": total_price}

    def _handle_confirm_price(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Подтверждение цены от Агрегатора — фиксируем заказ у оператора."""
        payload = message.get("payload", {}) or {}
        if isinstance(payload, (str, bytes)):
            payload = json.loads(payload)

        order_id = message.get("correlation_id", "") or payload.get("order_id", "")
        operator_id = payload.get("operator_id", "")
        accepted_price = payload.get("accepted_price", 0)

        logger.info("[%s] confirm_price order=%s operator=%s price=%s",
                    self.component_id, order_id, operator_id, accepted_price)
        return {
            "status": "confirmed",
            "order_id": order_id,
            "accepted_price": accepted_price,
        }

    # ------------------------------------------------------------------
    # Полётная миссия: автоматическая регистрация и авторизация в ORVD
    # ------------------------------------------------------------------

    def start(self):
        """Подписывается на свой топик + канал GCS drone_manager."""
        super().start()
        # GCS публикует mission.upload в gcs.components.drone_manager при
        # task.assign. Operator должен зарегистрировать миссию в ORVD под
        # тем же mission_id, иначе autopilot.request_takeoff получит
        # 'mission not found' и cmd=START завершится ABORTED.
        ok = self.bus.subscribe(ExternalTopics.GCS_DRONE_MANAGER, self._on_gcs_drone_manager_event)
        logger.info("[%s] subscribe %s: %s", self.component_id, ExternalTopics.GCS_DRONE_MANAGER, ok)

    def _on_gcs_drone_manager_event(self, message: Dict[str, Any]) -> None:
        action = message.get("action")
        if action != "mission.upload":
            return
        payload = message.get("payload", {}) or {}
        try:
            self._register_and_authorize_flight_mission(payload)
        except Exception as exc:
            logger.warning(
                "[%s] flight mission registration failed: %s",
                self.component_id, exc,
            )

    def _register_and_authorize_flight_mission(self, payload: Dict[str, Any]) -> None:
        mission_id = payload.get("mission_id")
        drone_id = payload.get("drone_id")
        if not mission_id or not drone_id:
            return
        wpl = payload.get("wpl_content") or payload.get("wpl") or ""
        route = self._parse_wpl_route(wpl)
        if not route:
            logger.warning("[%s] flight mission %s has empty route from WPL",
                           self.component_id, mission_id)
            return

        # Publish home to SITL: разрывает deadlock autopilot._step_control,
        # который ждёт nav_state, а nav_state приходит только после DronePort
        # takeoff (после home в SITL). Первая waypoint = home.
        self.bus.publish(
            "sitl-drone-home",
            {
                "drone_id": drone_id,
                "home_lat": route[0]["lat"],
                "home_lon": route[0]["lon"],
                "home_alt": 50.0,
            },
        )

        reg = self.bus.request(
            ExternalTopics.ORVD,
            {
                "action": "register_mission",
                "sender": self.topic,
                "payload": {"mission_id": mission_id, "drone_id": drone_id, "route": route},
            },
            timeout=self.EXTERNAL_REQUEST_TIMEOUT,
        )
        reg_pl = (reg or {}).get("payload") or {}
        if not reg or reg_pl.get("status") not in ("mission_registered", "registered"):
            logger.warning(
                "[%s] ORVD register_mission failed for %s: %s",
                self.component_id, mission_id, reg,
            )
            return

        auth = self.bus.request(
            ExternalTopics.ORVD,
            {
                "action": "authorize_mission",
                "sender": self.topic,
                "payload": {"mission_id": mission_id},
            },
            timeout=self.EXTERNAL_REQUEST_TIMEOUT,
        )
        auth_pl = (auth or {}).get("payload") or {}
        logger.info(
            "[%s] flight mission %s ORVD reg=%s auth=%s drone=%s",
            self.component_id, mission_id,
            reg_pl.get("status"), auth_pl.get("status"), drone_id,
        )

    @staticmethod
    def _parse_wpl_route(wpl: str) -> list:
        """QGC WPL 110 → [{lat, lon}, ...]."""
        route: list = []
        for line in (wpl or "").splitlines():
            parts = line.split("\t")
            if len(parts) < 12:
                continue
            try:
                lat = float(parts[8])
                lon = float(parts[9])
            except (ValueError, IndexError):
                continue
            route.append({"lat": lat, "lon": lon})
        return route
