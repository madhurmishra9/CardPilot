"""Card Recommendation Engine (Module D, Phase 3). Pure functions, zero I/O.

Simulates each catalog card against the user's real spend profile and ranks by
projected annual NET value: earn + milestones + quantified perks − annual fee
(unless waiver met) − amortized joining fee. Every result carries honest
caveats (merchant-restricted rates, spend-gated perks, caps).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import rules_engine as eng

JOINING_FEE_AMORTIZATION_YEARS = 3
ASSUMED_MAX_LOUNGE_VISITS_USED = 8  # per year, keeps perk value honest


@dataclass
class CardSimulation:
    card_id: str
    display_name: str
    annual_net_value: float
    lifetime_free: bool
    fee_waivable: bool
    charges_flag: str          # "lifetime-free" | "fee waived at your spend" | "₹X fee applies"
    earn_inr: float
    milestone_inr: float
    perks_inr: float
    annual_fee_inr: float
    joining_fee_amortized_inr: float
    earn_by_category: dict = field(default_factory=dict)
    caveats: list[str] = field(default_factory=list)


def _capped_points(spend: float, entry: dict, caveats: list[str], cat: str) -> float:
    rate = float(entry.get("rate_points_per_100", 0))
    points = spend / 100 * rate
    cap = entry.get("monthly_cap_points")
    if cap is not None and points > cap * 12:
        points = float(cap) * 12
        caveats.append(f"{cat}: earn capped at {cap:g} pts/month")
    return points


def _annual_earn(rules: dict, category_spend: dict[str, float],
                 merchant_share: float = 1.0) -> tuple[float, dict, list[str]]:
    """Approximate annual points value per category (no per-txn slab granularity).

    `merchant_share`: fraction of a category's spend assumed to hit a
    merchant-restricted accelerated rate (e.g. 5% "on Amazon"); the rest earns
    the card's default rate. 1.0 = optimistic, 0.0 = ignore restricted rates.
    """
    pv = float(rules.get("point_value_inr", 0) or 0)
    rates = (rules.get("earn_rules") or {}).get("rates") or []
    excluded = (rules.get("earn_rules") or {}).get("excluded_categories") or []
    default = next((r for r in rates if r.get("category") == "retail_default"), None)

    total = 0.0
    by_cat: dict[str, float] = {}
    caveats: list[str] = []
    for cat, spend in category_spend.items():
        if spend <= 0:
            continue
        if cat in excluded:
            by_cat[cat] = 0.0
            continue
        entry = next((r for r in rates if r.get("category") == cat), default)
        if entry is None:
            by_cat[cat] = 0.0
            continue
        if entry.get("merchants") and merchant_share < 1.0:
            points = _capped_points(spend * merchant_share, entry, caveats, cat)
            if default is not None and default is not entry:
                points += spend * (1 - merchant_share) / 100 \
                    * float(default.get("rate_points_per_100", 0))
            caveats.append(
                f"{cat}: assumes {merchant_share:.0%} of spend at "
                f"{', '.join(entry['merchants'])}, rest at the default rate")
        else:
            points = _capped_points(spend, entry, caveats, cat)
            if entry.get("merchants"):
                caveats.append(f"{cat}: accelerated rate only at "
                               f"{', '.join(entry['merchants'])} — assumed for all "
                               f"{cat} spend")
        value = round(points * pv, 2)
        by_cat[cat] = value
        total += value
    return round(total, 2), by_cat, caveats


def _annual_milestones(rules: dict, total_spend: float) -> float:
    ms = rules.get("milestones") or {}
    pv = float(rules.get("point_value_inr", 0) or 0)
    if not ms.get("tiers"):
        return 0.0
    if ms.get("period") == "calendar_quarter":
        return round(eng.milestone_bonus_total(rules, total_spend / 4) * 4 * pv, 2)
    return round(eng.milestone_bonus_total(rules, total_spend) * pv, 2)


def _annual_perks(rules: dict, category_spend: dict[str, float],
                  total_spend: float) -> tuple[float, list[str]]:
    perks = rules.get("perks") or {}
    total = 0.0
    caveats: list[str] = []

    fuel = perks.get("fuel_surcharge_waiver")
    fuel_spend = category_spend.get("fuel", 0)
    if fuel and fuel_spend:
        total += fuel_spend * float(fuel.get("rate", 0))
        if fuel.get("merchants"):
            caveats.append(f"fuel surcharge waiver only at {', '.join(fuel['merchants'])}")

    quarter_spend = total_spend / 4
    for name, perk in perks.items():
        if not name.startswith("lounge_") or not isinstance(perk, dict):
            continue
        visits = float(perk.get("count_per_year", 0) or 0) or \
            float(perk.get("count_per_quarter", 0) or 0) * 4
        gate = perk.get("unlock_spend_prev_quarter")
        if gate and quarter_spend < float(gate):
            caveats.append(f"{name}: needs ₹{float(gate):,.0f}/quarter spend "
                           f"(you average ₹{quarter_spend:,.0f}) — not counted")
            continue
        visits = min(visits, ASSUMED_MAX_LOUNGE_VISITS_USED)
        total += visits * float(perk.get("value_per_visit_inr", 0) or 0)
    return round(total, 2), caveats


def simulate_card(rules: dict, category_spend: dict[str, float],
                  held: bool = False, merchant_share: float = 1.0) -> CardSimulation:
    """Project one card's annual net value on the user's actual spend."""
    total_spend = sum(category_spend.values())
    earn_inr, by_cat, caveats = _annual_earn(rules, category_spend, merchant_share)
    milestone_inr = _annual_milestones(rules, total_spend)
    perks_inr, perk_caveats = _annual_perks(rules, category_spend, total_spend)
    caveats += perk_caveats

    fee = eng.effective_annual_fee(rules, total_spend)
    joining = 0.0
    if not held and not rules.get("lifetime_free"):
        joining = round(float(rules.get("joining_fee", 0) or 0)
                        / JOINING_FEE_AMORTIZATION_YEARS, 2)

    waiver = float(rules.get("annual_fee_waiver_spend", 0) or 0)
    fee_waivable = bool(rules.get("annual_fee", 0)) and waiver > 0
    if rules.get("lifetime_free"):
        charges = "lifetime-free"
    elif fee == 0 and fee_waivable:
        charges = f"₹{float(rules.get('annual_fee', 0)):,.0f} fee waived at your spend"
    elif fee_waivable:
        need = waiver - total_spend
        charges = f"₹{fee:,.0f} fee applies (waived if you spend ₹{need:,.0f} more/yr)"
    else:
        charges = f"₹{fee:,.0f} fee applies (not waivable)" if fee else "no annual fee"

    exp_fee = float(rules.get("redemption_fee_inr", 0) or 0)
    if exp_fee:
        caveats.append(f"₹{exp_fee:g}+GST fee per redemption request — batch redemptions")

    net = round(earn_inr + milestone_inr + perks_inr - fee - joining, 2)
    return CardSimulation(
        card_id=rules.get("card_id", "?"),
        display_name=rules.get("display_name", rules.get("card_id", "?")),
        annual_net_value=net,
        lifetime_free=bool(rules.get("lifetime_free")),
        fee_waivable=fee_waivable,
        charges_flag=charges,
        earn_inr=earn_inr,
        milestone_inr=milestone_inr,
        perks_inr=perks_inr,
        annual_fee_inr=fee,
        joining_fee_amortized_inr=joining,
        earn_by_category=by_cat,
        caveats=caveats,
    )


def rank_cards(catalog: dict[str, dict], category_spend: dict[str, float],
               current_card_id: str | None = None,
               ltf_only: bool = False, merchant_share: float = 1.0) -> list[dict]:
    """Simulate every catalog card and rank vs the user's current card."""
    current_net = None
    if current_card_id and current_card_id in catalog:
        current_net = simulate_card(catalog[current_card_id], category_spend,
                                    held=True,
                                    merchant_share=merchant_share).annual_net_value

    results = []
    for card_id, rules in catalog.items():
        if ltf_only and not rules.get("lifetime_free"):
            continue
        sim = simulate_card(rules, category_spend, held=(card_id == current_card_id),
                            merchant_share=merchant_share)
        row = sim.__dict__ | {"is_current": card_id == current_card_id}
        if current_net is not None:
            row["delta_vs_current_inr"] = round(sim.annual_net_value - current_net, 2)
        results.append(row)
    return sorted(results, key=lambda r: r["annual_net_value"], reverse=True)


# ---------------------------------------------------------------------------
# Portfolio optimization: nobody optimal holds one card
# ---------------------------------------------------------------------------

def _category_rate_value(rules: dict, category: str) -> float:
    """₹ value per ₹100 spent in a category on this card (0 if excluded)."""
    er = rules.get("earn_rules") or {}
    if category in (er.get("excluded_categories") or []):
        return 0.0
    rates = er.get("rates") or []
    entry = next((r for r in rates if r.get("category") == category),
                 next((r for r in rates if r.get("category") == "retail_default"), None))
    if entry is None:
        return 0.0
    return float(entry.get("rate_points_per_100", 0)) \
        * float(rules.get("point_value_inr", 0) or 0)


def rank_portfolios(catalog: dict[str, dict], category_spend: dict[str, float],
                    size: int = 2, ltf_only: bool = False, top_n: int = 5,
                    merchant_share: float = 1.0) -> list[dict]:
    """Rank card COMBINATIONS: each category is routed to the combo's best card,
    then each card is simulated on only its assigned spend (so fees, caps,
    milestones and gated perks reflect the split, not the full wallet)."""
    from itertools import combinations

    eligible = {cid: r for cid, r in catalog.items()
                if not ltf_only or r.get("lifetime_free")}
    results = []
    for combo in combinations(sorted(eligible), size):
        assignment: dict[str, str] = {}
        spend_by_card: dict[str, dict[str, float]] = {cid: {} for cid in combo}
        for cat, spend in category_spend.items():
            if spend <= 0:
                continue
            best = max(combo, key=lambda cid: _category_rate_value(eligible[cid], cat))
            assignment[cat] = best
            spend_by_card[best][cat] = spend

        total, per_card = 0.0, []
        for cid in combo:
            sim = simulate_card(eligible[cid], spend_by_card[cid],
                                merchant_share=merchant_share)
            total += sim.annual_net_value
            per_card.append({
                "card_id": cid,
                "display_name": sim.display_name,
                "annual_net_value": sim.annual_net_value,
                "charges_flag": sim.charges_flag,
                "assigned_categories": sorted(spend_by_card[cid]),
                "assigned_spend": round(sum(spend_by_card[cid].values()), 2),
            })
        results.append({
            "cards": list(combo),
            "annual_net_value": round(total, 2),
            "assignment": assignment,
            "per_card": per_card,
            "caveat": ("Greedy per-category routing by earn rate — milestone "
                       "interplay across cards is approximated, not optimized."),
        })
    results.sort(key=lambda r: float(r["annual_net_value"]), reverse=True)  # type: ignore[arg-type]
    return results[:top_n]
