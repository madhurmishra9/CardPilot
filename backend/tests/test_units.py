"""Unit tests beyond the §9 acceptance suite: categorization, parsers, redemption."""

from datetime import date

from app.catalog import load_card_rules, load_categories
from app.parsers import generic_csv, icici_pdf
from app.services import categorize as cat
from app.services import redemption as red
from app.services import rules_engine as eng

CATALOG = load_card_rules()
CATEGORIES = load_categories()
CORAL = CATALOG["icici_coral"]


class TestCategorize:
    def test_keyword_match(self):
        assert cat.categorize("SWIGGY BANGALORE", CATEGORIES) == "dining"
        assert cat.categorize("HPCL PETROL PUMP", CATEGORIES) == "fuel"
        assert cat.categorize("AMAZON PAY INDIA", CATEGORIES) == "online_shopping"

    def test_mcc_beats_keywords(self):
        assert cat.categorize("SOME STORE", CATEGORIES, mcc=5411) == "groceries"

    def test_learned_mapping_wins(self):
        learned = {"swiggy instamart": "groceries"}
        assert cat.categorize("SWIGGY INSTAMART", CATEGORIES, learned=learned) == "groceries"

    def test_unknown_falls_back_to_default(self):
        assert cat.categorize("RANDOM SHOP 42", CATEGORIES) == "retail_default"


class TestCsvParser:
    CSV = (b"Txn Date,Details,Amount\n"
           b"01/06/2026,SWIGGY BANGALORE,\"1,234.56\"\n"
           b"02/06/2026,REFUND AMAZON,-500.00\n"
           b"03/06/2026,HPCL FUEL,2000.00\n")
    MAPPING = {"date": "Txn Date", "amount": "Amount", "merchant": "Details"}

    def test_parses_debits_and_skips_credits(self):
        rows = generic_csv.parse(self.CSV, self.MAPPING)
        assert len(rows) == 2
        assert rows[0] == {"date": date(2026, 6, 1), "amount": 1234.56,
                           "merchant_raw": "SWIGGY BANGALORE"}


class TestIciciPdfLineParser:
    def test_parses_debit_row(self):
        rows = icici_pdf.parse_line("03/06/2026  SWIGGY BANGALORE IN  1,234.56")
        assert rows == [{"date": date(2026, 6, 3), "amount": 1234.56,
                         "merchant_raw": "SWIGGY BANGALORE IN"}]

    def test_skips_credit_and_noise(self):
        assert icici_pdf.parse_line("04/06/2026  PAYMENT RECEIVED  5,000.00 CR") == []
        assert icici_pdf.parse_line("Statement period: June 2026") == []


class TestRedemption:
    def test_fee_includes_gst(self):
        assert red.redemption_fee_total(CORAL) == 116.82  # 99 × 1.18

    def test_break_even(self):
        # 116.82 / 0.25 → 468 points minimum for a request to be worth anything
        assert red.break_even_points(CORAL) == 468

    def test_rank_options_deducts_fee(self):
        options = [
            {"name": "Voucher", "type": "voucher", "points_required": 2000, "inr_value": 500},
            {"name": "Flight", "type": "flight", "points_required": 8000, "inr_value": 2240},
        ]
        ranked = red.rank_options(CORAL, options, points_available=10000)
        assert ranked[0].name == "Flight"  # 0.265/pt beats 0.192/pt net of fee
        assert ranked[0].net_value_inr == 2240 - 116.82

    def test_unaffordable_options_excluded(self):
        options = [{"name": "Big", "type": "product", "points_required": 50000,
                    "inr_value": 12000}]
        assert red.rank_options(CORAL, options, points_available=1000) == []

    def test_redeem_vs_hold_forces_redeem_on_expiry(self):
        lots = [{"points": 5000, "earned_on": date(2023, 9, 1)}]
        options = [{"name": "Voucher", "type": "voucher", "points_required": 2000,
                    "inr_value": 500}]
        decision = red.redeem_vs_hold(CORAL, options, 5000, lots, as_of=date(2026, 7, 3))
        assert decision.action == "redeem"


class TestEngineEdges:
    def test_no_expiry_when_points_never_expire(self):
        ltf = CATALOG["amazon_pay_icici"]  # points_expiry_months: 0
        lots = [{"points": 1000, "earned_on": date(2020, 1, 1)}]
        assert red.expiry_alerts(ltf, lots, as_of=date(2026, 7, 3)) == []

    def test_monthly_cap_applied(self):
        sbi = CATALOG["sbi_cashback"]
        result = eng.points_earned(sbi, "online_shopping", 200000)
        assert result.points == 5000  # 5% capped at 5000/month

    def test_annual_fee_waiver(self):
        assert eng.effective_annual_fee(CORAL, year_spend=150000) == 0.0
        assert eng.effective_annual_fee(CORAL, year_spend=100000) == 590.0  # 500+GST
        assert eng.effective_annual_fee(CATALOG["amazon_pay_icici"], 0) == 0.0

    def test_perk_gate_progress(self):
        gates = eng.perk_gate_progress(CORAL, quarter_spend=67000, year_spend=132000)
        lounge = next(g for g in gates if g["perk"] == "lounge_domestic_airport")
        assert not lounge["unlocked"]
        assert lounge["spend_needed"] == 8000.0
        waiver = next(g for g in gates if g["perk"] == "annual_fee_waiver")
        assert waiver["spend_needed"] == 18000.0
