"""Unit-тесты для страховой математики alt_insurer."""
import pytest
from systems.alt_insurer.src.insurance_service.src.insurance_service import (
    _calc_kfleet_history,
    _calc_kincident_history,
    _calc_annual_premium,
    _calc_mission_premium,
    InsuranceService,
)


# ─── Kfleet_history ────────────────────────────────────────────────────────────

class TestKfleetHistory:
    def test_less_than_10_flights_returns_1(self):
        assert _calc_kfleet_history(5, 0.0) == 1.0

    def test_high_accident_rate_returns_penalty(self):
        assert _calc_kfleet_history(200, 0.06) == 1.5

    def test_good_history_returns_discount(self):
        assert _calc_kfleet_history(150, 0.01) == 0.8

    def test_intermediate_returns_neutral(self):
        # 50 полётов, аварийность 3% — не попадает ни в одну льготную категорию
        assert _calc_kfleet_history(50, 0.03) == 1.0


# ─── Kincident_history ─────────────────────────────────────────────────────────

class TestKincidentHistory:
    def test_no_missions_returns_kbase(self):
        assert _calc_kincident_history(0, 0) == 1.0

    def test_ideal_history_500_missions(self):
        # N >= 500 и incidents == 0 → kbase = 0.8
        assert _calc_kincident_history(0, 500) == 0.8

    def test_formula(self):
        # incidents=2, total=100, L=2.0, kbase=1.0 → 1.0 + 2/100*2 = 1.04
        result = _calc_kincident_history(2, 100, leverage=2.0, kbase=1.0)
        assert abs(result - 1.04) < 1e-9


# ─── Annual premium ────────────────────────────────────────────────────────────

class TestAnnualPremium:
    def test_basic(self):
        # 1_000_000 * 0.08 * 1.0 = 80_000
        p = _calc_annual_premium(1_000_000, 0.08, 5, 0.0)
        assert p == 80_000.0

    def test_discount_applied(self):
        # 1_000_000 * 0.08 * 0.8 = 64_000
        p = _calc_annual_premium(1_000_000, 0.08, 150, 0.01)
        assert p == 64_000.0

    def test_penalty_applied(self):
        # 1_000_000 * 0.08 * 1.5 = 120_000
        p = _calc_annual_premium(1_000_000, 0.08, 200, 0.06)
        assert p == 120_000.0

    def test_rate_clamped_to_min(self):
        p_low  = _calc_annual_premium(100_000, 0.01, 5, 0.0)  # clamped to 0.05
        p_base = _calc_annual_premium(100_000, 0.05, 5, 0.0)
        assert p_low == p_base

    def test_rate_clamped_to_max(self):
        p_high = _calc_annual_premium(100_000, 0.99, 5, 0.0)  # clamped to 0.15
        p_base = _calc_annual_premium(100_000, 0.15, 5, 0.0)
        assert p_high == p_base


# ─── Mission premium ───────────────────────────────────────────────────────────

class TestMissionPremium:
    def test_inspector_drone(self):
        # 50_000 * 0.01 * 1.0 * 1.0 = 500
        p = _calc_mission_premium(50_000, "inspector", 1.0, 0, 10)
        assert p == 500.0

    def test_delivery_drone(self):
        # 50_000 * 0.08 * 1.0 * 1.0 = 4_000
        p = _calc_mission_premium(50_000, "delivery", 1.0, 0, 10)
        assert p == 4_000.0

    def test_firefighter_drone(self):
        # 50_000 * 0.12 * 1.0 * 1.0 = 6_000
        p = _calc_mission_premium(50_000, "firefighter", 1.0, 0, 10)
        assert p == 6_000.0

    def test_kenv_applied(self):
        # 50_000 * 0.08 * 2.0 * 1.0 = 8_000
        p = _calc_mission_premium(50_000, "delivery", 2.0, 0, 10)
        assert p == 8_000.0

    def test_kenv_clamped(self):
        p_high = _calc_mission_premium(50_000, "delivery", 5.0, 0, 10)  # clamped to 2.0
        p_max  = _calc_mission_premium(50_000, "delivery", 2.0, 0, 10)
        assert p_high == p_max

    def test_unknown_drone_type_defaults_to_delivery(self):
        p = _calc_mission_premium(50_000, "unknown_type", 1.0, 0, 10)
        assert p == _calc_mission_premium(50_000, "delivery", 1.0, 0, 10)


# ─── InsuranceService handlers ─────────────────────────────────────────────────

class FakeBus:
    def subscribe(self, *a, **kw): pass
    def unsubscribe(self, *a, **kw): pass
    def publish(self, *a, **kw): pass
    def request(self, *a, **kw): return None
    def start(self): pass
    def stop(self): pass


@pytest.fixture
def service():
    svc = InsuranceService.__new__(InsuranceService)
    svc._policies = {}
    svc._incidents = {}
    svc._drone_stats = {}
    svc.component_id = "test_insurer"
    svc._handlers = {}
    svc._running = False
    svc.bus = FakeBus()
    svc._register_handlers()
    return svc


class TestInsuranceServiceHandlers:
    def test_annual_creates_policy(self, service):
        msg = {"action": "annual_insurance", "payload": {
            "order_id": "ord-1", "drone_id": "d-1",
            "drone_value": 500_000, "base_hull_rate": 0.10,
            "coverage_amount": 500_000,
        }}
        resp = service._handle_annual(msg)
        assert resp["policy_id"] is not None
        assert resp["policy_type"] == "annual"
        # flights=0 < 10 → k=1.0 → 500_000 * 0.10 * 1.0 = 50_000
        assert resp["premium"] == 50_000.0

    def test_annual_premium_no_history(self, service):
        msg = {"payload": {
            "order_id": "ord-2", "drone_id": "d-2",
            "drone_value": 1_000_000, "base_hull_rate": 0.08,
        }}
        resp = service._handle_annual(msg)
        # flights=0 < 10 → k=1.0 → 1_000_000 * 0.08 * 1.0 = 80_000
        assert resp["premium"] == 80_000.0

    def test_mission_increments_total_missions(self, service):
        msg = {"payload": {
            "order_id": "ord-3", "drone_id": "d-3",
            "drone_type": "delivery", "coverage_amount": 100_000,
            "kenv": 1.0,
        }}
        service._handle_mission(msg)
        service._handle_mission(msg)
        assert service._drone_stats["d-3"]["total_missions"] == 2

    def test_incident_updates_stats(self, service):
        service._drone_stats["d-4"] = {
            "flights_per_year": 50, "accident_rate": 0.0,
            "incidents": 0, "total_missions": 50,
        }
        msg = {"payload": {
            "order_id": "ord-4", "drone_id": "d-4",
            "incident": {"damage_amount": 15_000},
        }}
        resp = service._handle_incident(msg)
        assert service._drone_stats["d-4"]["incidents"] == 1
        assert resp["payment_amount"] == 15_000.0

    def test_terminate_policy(self, service):
        service._policies["p-1"] = {
            "order_id": "ord-5", "status": "active", "policy_type": "annual"
        }
        msg = {"payload": {"order_id": "ord-5"}}
        resp = service._handle_terminate(msg)
        assert "прекращён" in resp["message"]
        assert service._policies["p-1"]["status"] == "terminated"

    def test_terminate_not_found(self, service):
        msg = {"payload": {"order_id": "no-such-order"}}
        resp = service._handle_terminate(msg)
        assert resp.get("error") is True
