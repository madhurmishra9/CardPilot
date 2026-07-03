"""Tests for Phases 3–5: recommendation engine, travel savings, chat, nudges."""

from datetime import date, timedelta

import pytest

from app.catalog import load_card_rules
from app.providers.fare_provider import MockFareProvider
from app.providers.llm_provider import NullProvider, get_llm_provider
from app.services import recommend, travel
from app.services.chat import route_intent, _extract_amount, _extract_category

CATALOG = load_card_rules()
CORAL = CATALOG["icici_coral"]


class TestRecommendEngine:
    ONLINE_HEAVY = {"online_shopping": 300000, "retail_default": 100000}
    UTILITY_HEAVY = {"utilities": 200000, "insurance": 100000, "retail_default": 50000}

    def test_online_heavy_prefers_cashback_over_coral(self):
        ranked = recommend.rank_cards(CATALOG, self.ONLINE_HEAVY,
                                      current_card_id="icici_coral")
        ids = [r["card_id"] for r in ranked]
        assert ids.index("sbi_cashback") < ids.index("icici_coral")
        top = ranked[0]
        assert top["delta_vs_current_inr"] > 0
        assert top["annual_net_value"] == pytest.approx(
            top["earn_inr"] + top["milestone_inr"] + top["perks_inr"]
            - top["annual_fee_inr"] - top["joining_fee_amortized_inr"], abs=0.01)

    def test_coral_beats_utility_excluders_on_utility_spend(self):
        ranked = recommend.rank_cards(CATALOG, self.UTILITY_HEAVY)
        by_id = {r["card_id"]: r for r in ranked}
        # SBI Cashback excludes utilities+insurance → earns almost nothing here
        assert by_id["icici_coral"]["earn_inr"] > by_id["sbi_cashback"]["earn_inr"]

    def test_ltf_filter(self):
        ranked = recommend.rank_cards(CATALOG, self.ONLINE_HEAVY, ltf_only=True)
        assert ranked
        assert all(r["lifetime_free"] for r in ranked)

    def test_annual_fee_subtracted_unless_waiver_met(self):
        # Atlas fee is not waivable → always subtracted (with GST)
        sim = recommend.simulate_card(CATALOG["axis_atlas"],
                                      {"retail_default": 100000}, held=True)
        assert sim.annual_fee_inr == 5900.0
        # Coral at ₹2L spend → waiver met
        sim2 = recommend.simulate_card(CORAL, {"retail_default": 200000}, held=True)
        assert sim2.annual_fee_inr == 0.0

    def test_merchant_restricted_rate_carries_caveat(self):
        sim = recommend.simulate_card(CATALOG["amazon_pay_icici"],
                                      {"online_shopping": 100000})
        assert any("amazon" in c.lower() for c in sim.caveats)

    def test_gated_lounge_not_counted_below_gate(self):
        low = recommend.simulate_card(CORAL, {"retail_default": 100000}, held=True)
        high = recommend.simulate_card(CORAL, {"retail_default": 400000}, held=True)
        assert high.perks_inr > low.perks_inr  # ₹75k/qtr lounge gate crossed


class TestTravel:
    def test_mock_provider_deterministic(self):
        p = MockFareProvider()
        a = p.search("BOM", "BKK", date(2026, 9, 1))
        b = p.search("BOM", "BKK", date(2026, 9, 1))
        assert [f.price_inr for f in a] == [f.price_inr for f in b]
        assert a[0].price_inr <= a[-1].price_inr

    def test_best_card_effective_cost(self):
        ranked = travel.best_card_for_booking([CORAL, CATALOG["axis_atlas"]], 42000)
        assert ranked[0]["card_id"] == "axis_atlas"  # 5 miles/₹100 @ ₹1 vs 2RP @ ₹0.25
        assert ranked[0]["effective_cost_inr"] == 42000 - ranked[0]["net_value_inr"]

    def test_points_vs_cash_paths(self):
        options = [{"type": "flight", "points_required": 8000, "inr_value": 2240}]
        paths = travel.points_vs_cash(CORAL, 10000, points_balance=50000,
                                      flight_redemption_options=options)
        by = {p.path: p for p in paths}
        assert by["cash"].feasible
        assert by["points"].feasible
        assert by["points"].value_per_point == 0.28
        assert any("cheapest path" in p.explanation for p in paths)

    def test_points_path_infeasible_when_balance_short(self):
        paths = travel.points_vs_cash(CORAL, 10000, points_balance=100)
        by = {p.path: p for p in paths}
        assert not by["points"].feasible

    def test_trend_advice(self):
        assert travel.fare_trend_advice([5000]).action == "insufficient_history"
        assert travel.fare_trend_advice([6000, 5500, 5200, 4800]).action == "book_now"
        assert travel.fare_trend_advice([4000, 4200, 4800, 5200]).action == "book_soon"
        assert travel.fare_trend_advice([4000, 5200, 4900, 4600]).action == "wait"


class TestChatRouting:
    def test_intents(self):
        assert route_intent("Which card for a 42k flight to Bangkok?") == "swipe"
        assert route_intent("Should I redeem my points now?") == "redeem"
        assert route_intent("How close am I to the lounge benefit?") == "progress"
        assert route_intent("Is there a better card for me?") == "recommend"
        assert route_intent("hello") == "help"

    def test_amount_extraction(self):
        assert _extract_amount("a ₹42k flight") == 42000
        assert _extract_amount("spend 1.5 lakh") == 150000
        assert _extract_amount("Rs 5,000 groceries") == 5000

    def test_category_extraction(self):
        assert _extract_category("flight to Bangkok") == "travel"
        assert _extract_category("petrol at HPCL") == "fuel"

    def test_default_provider_is_grounded_null(self):
        provider = get_llm_provider()
        assert isinstance(provider, NullProvider)
        assert provider.explain("q", "FACTS") == "FACTS"
