"""Tests for the enhancement round: aggregate caps, merchant-share assumption,
portfolio recommendation, realized value, devaluation history, staleness."""


import pytest

from app.catalog import load_card_rules
from app.services import recommend, rules_history
from app.services import rules_engine as eng

CATALOG = load_card_rules()
CORAL = CATALOG["icici_coral"]
SBI_CB = CATALOG["sbi_cashback"]


class TestAggregateMonthlyCap:
    def test_cap_enforced_across_month(self):
        # SBI Cashback: 5%/online capped at 5000/month. ₹60k earns 3000;
        # a second ₹60k the same month has only 2000 headroom left.
        first = eng.points_earned(SBI_CB, "online_shopping", 60000)
        assert first.points == 3000
        second = eng.points_earned(SBI_CB, "online_shopping", 60000,
                                   prior_month_points=3000)
        assert second.points == 2000
        assert "already earned this month" in second.reason
        third = eng.points_earned(SBI_CB, "online_shopping", 10000,
                                  prior_month_points=5000)
        assert third.points == 0

    def test_no_cap_ignores_prior(self):
        result = eng.points_earned(CORAL, "groceries", 5000, prior_month_points=99999)
        assert result.points == 100


class TestMerchantShare:
    def test_share_splits_between_restricted_and_default(self):
        # Amazon Pay ICICI: 5% at Amazon, 1% default. 60% share on ₹100k online:
        # 60k×5% + 40k×1% = 3000 + 400 pts (₹3400 at 1.0/pt)
        sim = recommend.simulate_card(CATALOG["amazon_pay_icici"],
                                      {"online_shopping": 100000},
                                      merchant_share=0.6)
        assert sim.earn_by_category["online_shopping"] == 3400.0
        assert any("60%" in c for c in sim.caveats)

    def test_full_share_matches_old_behavior(self):
        optimistic = recommend.simulate_card(CATALOG["amazon_pay_icici"],
                                             {"online_shopping": 100000},
                                             merchant_share=1.0)
        assert optimistic.earn_by_category["online_shopping"] == 5000.0


class TestPortfolio:
    SPEND = {"online_shopping": 200000, "utilities": 100000, "fuel": 60000,
             "dining": 60000}

    def test_portfolio_beats_best_single_card(self):
        singles = recommend.rank_cards(CATALOG, self.SPEND)
        duos = recommend.rank_portfolios(CATALOG, self.SPEND, size=2)
        assert duos[0]["annual_net_value"] >= singles[0]["annual_net_value"]

    def test_categories_routed_to_best_card(self):
        duos = recommend.rank_portfolios(CATALOG, self.SPEND, size=2)
        top = duos[0]
        # every spend category is assigned to exactly one card of the combo
        assert set(top["assignment"]) == set(self.SPEND)
        assert all(cid in top["cards"] for cid in top["assignment"].values())
        # per-card assigned spend adds back up to the profile
        assert sum(pc["assigned_spend"] for pc in top["per_card"]) == \
            pytest.approx(sum(self.SPEND.values()))

    def test_trio_and_ltf_filter(self):
        trios = recommend.rank_portfolios(CATALOG, self.SPEND, size=3, top_n=3)
        assert trios and all(len(p["cards"]) == 3 for p in trios)
        # only 2 LTF cards exist in the seed catalog → duo works, trio can't
        ltf_duos = recommend.rank_portfolios(CATALOG, self.SPEND, size=2,
                                             ltf_only=True)
        assert ltf_duos
        assert all(CATALOG[cid].get("lifetime_free")
                   for p in ltf_duos for cid in p["cards"])
        assert recommend.rank_portfolios(CATALOG, self.SPEND, size=3,
                                         ltf_only=True) == []


class TestRulesHistory:
    def test_coral_history_readable_from_git(self):
        history = rules_history.card_history("icici_coral")
        assert history, "expected at least the initial commit"
        assert history[-1]["changes"] == ["initial version of this card's rules"]

    def test_diff_detects_devaluation(self):
        older = {"point_value_inr": 0.25,
                 "earn_rules": {"rates": [{"category": "utilities",
                                           "rate_points_per_100": 1}],
                                "excluded_categories": []}}
        newer = {"point_value_inr": 0.20,
                 "earn_rules": {"rates": [{"category": "utilities",
                                           "rate_points_per_100": 0.5}],
                                "excluded_categories": ["rent"]}}
        changes = rules_history._diff_versions(older, newer)
        assert "point_value_inr: 0.25 → 0.2" in changes
        assert "earn rate 'utilities': 1.0 → 0.5 pts/₹100" in changes
        assert "'rent' newly EXCLUDED from rewards" in changes
