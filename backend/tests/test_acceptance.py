"""Acceptance tests from the build spec (§9), run against the real seed catalog.

These pin the reference behaviour of the rules engine on ICICI Coral rules.
"""

from datetime import date

import pytest

from app.catalog import load_card_rules
from app.services import redemption as red
from app.services import rules_engine as eng


@pytest.fixture(scope="module")
def catalog():
    return load_card_rules()


@pytest.fixture(scope="module")
def coral(catalog):
    return catalog["icici_coral"]


def test_1_groceries_earn(coral):
    """₹5,000 groceries on Coral → 100 RP (2/₹100) → ₹25 baseline value."""
    result = eng.points_earned(coral, "groceries", 5000)
    assert result.points == 100
    assert result.eligible
    value = eng.transaction_net_value(coral, "groceries", 5000)
    assert value.points_value_inr == 25.0


def test_2_utilities_half_rate(coral):
    """₹3,000 electricity bill on Coral → 30 RP (1/₹100, utilities half-rate)."""
    result = eng.points_earned(coral, "utilities", 3000)
    assert result.points == 30
    assert result.rate_per_100 == 1


def test_3_fuel_excluded_but_surcharge_waived(coral):
    """₹2,000 fuel on Coral → 0 RP (excluded) BUT 1% surcharge waiver at HPCL."""
    result = eng.points_earned(coral, "fuel", 2000, merchant="HPCL Pump Andheri")
    assert result.points == 0
    assert not result.eligible
    waiver = eng.surcharge_waiver_value(coral, "fuel", 2000, merchant="HPCL Pump Andheri")
    assert waiver == 20.0  # 1% of 2000, within ₹400–4000 band
    # outside the band or wrong merchant → no waiver
    assert eng.surcharge_waiver_value(coral, "fuel", 300, merchant="HPCL") == 0
    assert eng.surcharge_waiver_value(coral, "fuel", 2000, merchant="IOCL") == 0


def test_4_milestone_crossing(coral):
    """Cumulative spend crossing ₹2,00,000 in anniversary year → +2,000 bonus RP."""
    assert eng.milestone_bonus_total(coral, 199999) == 0
    assert eng.milestone_bonus_total(coral, 200000) == 2000
    assert eng.milestone_bonus_crossed(coral, 195000, 205000) == 2000
    # +1000 per extra 1L, capped at 10,000/year
    assert eng.milestone_bonus_total(coral, 300000) == 3000
    assert eng.milestone_bonus_total(coral, 2500000) == 10000
    # the swipe advisor surfaces the nudge
    value = eng.transaction_net_value(coral, "groceries", 10000, cumulative_spend=195000)
    assert value.milestone_bonus_inr == 500.0  # 2000 pts × ₹0.25
    assert value.milestone_note is not None


def test_5_split_redemption_warns(coral):
    """Redeeming 400 RP in two requests → warn: two ₹99+GST fees destroy value."""
    split = red.batching_advice(coral, total_points=400, n_requests=2)
    assert split.warn
    assert split.total_fees_inr == pytest.approx(2 * 99 * 1.18, abs=0.01)
    assert split.net_value_inr < 0  # ₹100 gross value vs ₹233.64 in fees
    assert "single" in split.recommendation.lower() or "batch" in split.recommendation.lower()
    single = red.batching_advice(coral, total_points=400, n_requests=1)
    assert single.net_value_inr > split.net_value_inr


def test_6_expiry_alert(coral):
    """Points earned 34 months ago → expiry alert (<90 days to 36-month expiry)."""
    as_of = date(2026, 7, 3)
    lots = [
        {"points": 4000, "earned_on": date(2023, 9, 10)},   # ~34 months ago → alert
        {"points": 1000, "earned_on": date(2026, 1, 1)},    # fresh → no alert
    ]
    alerts = red.expiry_alerts(coral, lots, as_of=as_of, window_days=90)
    assert len(alerts) == 1
    assert alerts[0].points == 4000
    assert alerts[0].days_left <= 90
    assert alerts[0].value_at_risk_inr == 1000.0  # 4000 × ₹0.25


def test_7_swipe_advisor_ranking(catalog, coral):
    """Fuel-accelerator card beats Coral on fuel; Coral wins utilities vs excluders."""
    octane = catalog["bpcl_sbi_octane"]
    sbi_cb = catalog["sbi_cashback"]

    fuel_rank = eng.rank_cards_for_spend([coral, octane], "fuel", 3000, merchant="BPCL")
    assert fuel_rank[0].card_id == "bpcl_sbi_octane"

    util_rank = eng.rank_cards_for_spend([coral, sbi_cb], "utilities", 3000)
    assert util_rank[0].card_id == "icici_coral"
    assert util_rank[0].net_value_inr > 0
    assert util_rank[1].net_value_inr == 0  # SBI Cashback excludes utilities

    # every recommendation shows its math
    assert fuel_rank[0].explanation and util_rank[0].explanation
