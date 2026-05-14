"""
InsuranceService — компонент страхования для alt_insurer.

Реализует страховую математику:
  - Pannual  = Vdrone × Rbase_hull × Kfleet_history
  - Pmission = (Vcargo × Rrisk_class) × Kenv × Kincident_history
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from sdk.base_component import BaseComponent
from broker.system_bus import SystemBus

from systems.alt_insurer.src.insurance_service.topics import (
    ComponentTopics,
    InsuranceActions,
)

# drone_type -> Rrisk_class
RISK_CLASS_RATES = {
    "inspector":   0.01,
    "delivery":    0.08,
    "firefighter": 0.12,
}

DEFAULT_LEVERAGE = 2.0


def _calc_kfleet_history(flights_per_year: int, accident_rate: float) -> float:
    """
    Kfleet_history:
      0.8  — >100 полётов и аварийность < 2%
      1.5  — аварийность > 5%
      1.0  — менее 10 полётов (статистика не накоплена) или промежуточный случай
    """
    if flights_per_year < 10:
        return 1.0
    if accident_rate > 0.05:
        return 1.5
    if flights_per_year > 100 and accident_rate < 0.02:
        return 0.8
    return 1.0


def _calc_kincident_history(
    incidents: int,
    total_missions: int,
    leverage: float = DEFAULT_LEVERAGE,
    kbase: float = 1.0,
) -> float:
    """
    Kincident_history = Kbase + (Incidents / TotalMissions) × L
    Kbase = 0.8 для бортов с идеальной историей (total_missions >= 500 и incidents == 0).
    """
    if total_missions >= 500 and incidents == 0:
        kbase = 0.8
    if total_missions == 0:
        return kbase
    return kbase + (incidents / total_missions) * leverage


def _calc_annual_premium(
    drone_value: float,
    base_hull_rate: float,
    flights_per_year: int,
    accident_rate: float,
) -> float:
    """Pannual = Vdrone × Rbase_hull × Kfleet_history"""
    base_hull_rate = max(0.05, min(0.15, base_hull_rate))
    k = _calc_kfleet_history(flights_per_year, accident_rate)
    return round(drone_value * base_hull_rate * k, 2)


def _calc_mission_premium(
    cargo_value: float,
    drone_type: str,
    kenv: float,
    incidents: int,
    total_missions: int,
    leverage: float = DEFAULT_LEVERAGE,
) -> float:
    """Pmission = (Vcargo × Rrisk_class) × Kenv × Kincident_history"""
    r = RISK_CLASS_RATES.get(drone_type.lower(), 0.08)
    kenv = max(1.0, min(2.0, kenv))
    k_inc = _calc_kincident_history(incidents, total_missions, leverage)
    return round(cargo_value * r * kenv * k_inc, 2)


class InsuranceService(BaseComponent):

    def __init__(self, component_id: str, bus: SystemBus, topic: str):
        # in-memory хранилища
        self._policies: Dict[str, Dict] = {}
        self._incidents: Dict[str, Dict] = {}
        # drone_id -> {"flights_per_year": int, "accident_rate": float, "incidents": int, "total_missions": int}
        self._drone_stats: Dict[str, Dict] = {}

        super().__init__(
            component_id=component_id,
            component_type="insurance_service",
            topic=topic,
            bus=bus,
        )

    def _register_handlers(self):
        self.register_handler(InsuranceActions.ANNUAL_INSURANCE,  self._handle_annual)
        self.register_handler(InsuranceActions.MISSION_INSURANCE, self._handle_mission)
        self.register_handler(InsuranceActions.CALCULATE_POLICY,  self._handle_calculate)
        self.register_handler(InsuranceActions.PURCHASE_POLICY,   self._handle_annual)
        self.register_handler(InsuranceActions.REPORT_INCIDENT,   self._handle_incident)
        self.register_handler(InsuranceActions.TERMINATE_POLICY,  self._handle_terminate)

    # ------------------------------------------------------------------ helpers

    def _drone_stats_for(self, drone_id: str) -> Dict:
        return self._drone_stats.setdefault(drone_id, {
            "flights_per_year": 0,
            "accident_rate": 0.0,
            "incidents": 0,
            "total_missions": 0,
        })

    def _build_response(self, payload: Dict, **extra) -> Dict:
        return {
            "response_id":   str(uuid.uuid4()),
            "request_id":    payload.get("request_id"),
            "order_id":      payload.get("order_id"),
            **extra,
        }

    # ------------------------------------------------------------------ handlers

    def _handle_calculate(self, message: Dict[str, Any]) -> Dict[str, Any]:
        p = message.get("payload", {})
        drone_id   = p.get("drone_id", "")
        stats      = self._drone_stats_for(drone_id)
        drone_type = p.get("drone_type", "delivery")

        annual = _calc_annual_premium(
            drone_value     = float(p.get("drone_value", 0)),
            base_hull_rate  = float(p.get("base_hull_rate", 0.08)),
            flights_per_year= int(stats["flights_per_year"]),
            accident_rate   = float(stats["accident_rate"]),
        )
        mission = _calc_mission_premium(
            cargo_value    = float(p.get("coverage_amount", 0)),
            drone_type     = drone_type,
            kenv           = float(p.get("kenv", 1.0)),
            incidents      = int(stats["incidents"]),
            total_missions = int(stats["total_missions"]),
            leverage       = float(p.get("leverage", DEFAULT_LEVERAGE)),
        )
        k_fleet = _calc_kfleet_history(stats["flights_per_year"], stats["accident_rate"])
        k_inc   = _calc_kincident_history(stats["incidents"], stats["total_missions"])

        return {
            **self._build_response(p),
            "premium":          annual,
            "mission_premium":  mission,
            "kfleet_history":   k_fleet,
            "kincident_history":k_inc,
            "coverage_amount":  p.get("coverage_amount"),
            "message":          "Расчёт выполнен успешно",
        }

    def _handle_annual(self, message: Dict[str, Any]) -> Dict[str, Any]:
        p      = message.get("payload", {})
        drone_id = p.get("drone_id", "")
        stats  = self._drone_stats_for(drone_id)

        # Совместимость с протоколом systems.insurer: внешние клиенты шлют
        # coverage_amount; используем его как drone_value, если drone_value
        # явно не задан.
        drone_value = p.get("drone_value")
        if drone_value in (None, 0):
            drone_value = p.get("coverage_amount", 0)

        premium = _calc_annual_premium(
            drone_value     = float(drone_value),
            base_hull_rate  = float(p.get("base_hull_rate", 0.08)),
            flights_per_year= int(stats["flights_per_year"]),
            accident_rate   = float(stats["accident_rate"]),
        )
        k_fleet = _calc_kfleet_history(stats["flights_per_year"], stats["accident_rate"])

        policy_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        policy = {
            "id":              policy_id,
            "policy_type":     "annual",
            "status":          "active",
            "order_id":        p.get("order_id"),
            "drone_id":        drone_id,
            "manufacturer_id": p.get("manufacturer_id"),
            "operator_id":     p.get("operator_id"),
            "start_date":      now.isoformat(),
            "end_date":        (now + timedelta(days=365)).isoformat(),
            "cost":            premium,
            "coverage_amount": p.get("coverage_amount"),
            "kfleet_history":  k_fleet,
        }
        self._policies[policy_id] = policy

        return {
            **self._build_response(p),
            "policy_id":      policy_id,
            "policy_type":    "annual",
            "status":         "active",
            "drone_id":       drone_id,
            "start_date":     policy["start_date"],
            "end_date":       policy["end_date"],
            "premium":        premium,
            "kfleet_history": k_fleet,
            "coverage_amount":p.get("coverage_amount"),
            "message":        "Годовой полис успешно оформлен",
        }

    def _handle_mission(self, message: Dict[str, Any]) -> Dict[str, Any]:
        p        = message.get("payload", {})
        drone_id = p.get("drone_id", "")
        stats    = self._drone_stats_for(drone_id)

        # учитываем взлёт
        stats["total_missions"] += 1

        premium = _calc_mission_premium(
            cargo_value    = float(p.get("coverage_amount", 0)),
            drone_type     = p.get("drone_type", "delivery"),
            kenv           = float(p.get("kenv", 1.0)),
            incidents      = int(stats["incidents"]),
            total_missions = int(stats["total_missions"]),
            leverage       = float(p.get("leverage", DEFAULT_LEVERAGE)),
        )
        k_inc = _calc_kincident_history(stats["incidents"], stats["total_missions"])

        policy_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        policy = {
            "id":              policy_id,
            "policy_type":     "mission",
            "status":          "active",
            "order_id":        p.get("order_id"),
            "drone_id":        drone_id,
            "start_date":      now.isoformat(),
            "end_date":        (now + timedelta(hours=24)).isoformat(),
            "cost":            premium,
            "coverage_amount": p.get("coverage_amount"),
            "kincident_history": k_inc,
        }
        self._policies[policy_id] = policy

        return {
            **self._build_response(p),
            "policy_id":         policy_id,
            "policy_type":       "mission",
            "status":            "active",
            "drone_id":          drone_id,
            "start_date":        policy["start_date"],
            "end_date":          policy["end_date"],
            "premium":           premium,
            "kincident_history": k_inc,
            "coverage_amount":   p.get("coverage_amount"),
            "message":           "Миссионный полис успешно оформлен",
        }

    def _handle_incident(self, message: Dict[str, Any]) -> Dict[str, Any]:
        p        = message.get("payload", {})
        incident = p.get("incident") or p
        drone_id = p.get("drone_id", incident.get("drone_id", ""))
        stats    = self._drone_stats_for(drone_id)

        # фиксируем инцидент
        stats["incidents"] += 1
        if stats["total_missions"] > 0:
            stats["accident_rate"] = stats["incidents"] / stats["total_missions"]

        incident_id = str(uuid.uuid4())
        damage = float(incident.get("damage_amount", 0))
        self._incidents[incident_id] = {
            "id":            incident_id,
            "drone_id":      drone_id,
            "order_id":      p.get("order_id"),
            "damage_amount": damage,
            "status":        "PROCESSED",
            "date":          datetime.now(timezone.utc).isoformat(),
        }

        new_k_fleet = _calc_kfleet_history(stats["flights_per_year"], stats["accident_rate"])
        new_k_inc   = _calc_kincident_history(stats["incidents"], stats["total_missions"])

        return {
            **self._build_response(p),
            "coverage_amount":    damage,
            "payment_amount":     damage,
            "new_kfleet_history": new_k_fleet,
            "new_kincident_history": new_k_inc,
            "message":            "Инцидент обработан, произведена выплата",
        }

    def _handle_terminate(self, message: Dict[str, Any]) -> Dict[str, Any]:
        p        = message.get("payload", {})
        order_id = p.get("order_id")

        terminated = False
        for pol in self._policies.values():
            if pol.get("order_id") == order_id and pol["status"] == "active":
                pol["status"] = "terminated"
                terminated = True

        if terminated:
            return {
                **self._build_response(p),
                "message": "Полис успешно прекращён",
            }
        return {
            **self._build_response(p),
            "message": f"Полис не найден или уже прекращён: order_id={order_id}",
            "error":   True,
        }
