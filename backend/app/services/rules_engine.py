"""CardPilot rules engine.

Pure function library: (spend + card rules) -> value. Zero I/O, zero DB access.
Card rules are dicts parsed from /data/cards/*.yaml — reward rates are NEVER
hardcoded here. Every result carries an explanation so the UI can show its math.

All monetary values are INR. `rules` always means one card's full rules dict.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

SLAB_INR = 100  # earn rates are expressed as points per ₹100 slab


# ---------------------------------------------------------------------------
# Earning
# ---------------------------------------------------------------------------

@dataclass
class EarnResult:
    points: float
    eligible: bool
    rate_per_100: float
    category_used: str
    reason: str


def _earn_rates(rules: dict) -> list[dict]:
    return (rules.get("earn_rules") or {}).get("rates") or []


def _excluded_categories(rules: dict) -> list[str]:
    return (rules.get("earn_rules") or {}).get("excluded_categories") or []


def _merchant_matches(entry: dict, merchant: str | None) -> bool:
    wanted = entry.get("merchants") or []
    if not wanted:
        return True
    if not merchant:
        return False
    m = merchant.lower()
    return any(w.lower() in m for w in wanted)


def points_earned(rules: dict, category: str, amount: float,
                  merchant: str | None = None,
                  prior_month_points: float | None = None) -> EarnResult:
    """Points for a single transaction, respecting exclusions and per-category rates.

    Points accrue per full ₹100 slab (bank-style): floor(amount / 100) * rate.
    `prior_month_points`: points already earned this calendar month in the same
    category on this card — when given, monthly caps are enforced across the
    month's aggregate rather than per transaction.
    """
    if category in _excluded_categories(rules):
        return EarnResult(0, False, 0.0, category,
                          f"'{category}' is excluded from rewards on this card")

    rate_entry = None
    for entry in _earn_rates(rules):
        if entry.get("category") == category and _merchant_matches(entry, merchant):
            rate_entry = entry
            break
    if rate_entry is None:
        for entry in _earn_rates(rules):
            if entry.get("category") == "retail_default":
                rate_entry = entry
                break
    if rate_entry is None:
        return EarnResult(0, True, 0.0, category, "no earn rate configured")

    rate = float(rate_entry.get("rate_points_per_100", 0))
    slabs = math.floor(amount / SLAB_INR)
    points = float(math.floor(slabs * rate))
    cap = rate_entry.get("monthly_cap_points")
    reason = (f"{rate:g} pts/₹{SLAB_INR} on '{rate_entry.get('category')}' "
              f"× {slabs} slabs = {points:g} pts")
    if cap is not None:
        headroom = float(cap) - (prior_month_points or 0.0)
        if points > headroom:
            points = max(0.0, headroom)
            reason += (f" (capped at {cap:g}/month"
                       + (f"; {prior_month_points:g} already earned this month"
                          if prior_month_points else "") + ")")
    return EarnResult(points, True, rate, str(rate_entry.get("category")), reason)


def surcharge_waiver_value(rules: dict, category: str, amount: float,
                           merchant: str | None = None) -> float:
    """INR value of the fuel surcharge waiver for this transaction, if applicable."""
    if category != "fuel":
        return 0.0
    perk = (rules.get("perks") or {}).get("fuel_surcharge_waiver")
    if not perk:
        return 0.0
    if not (float(perk.get("min_txn", 0)) <= amount <= float(perk.get("max_txn", math.inf))):
        return 0.0
    merchants = perk.get("merchants") or []
    if merchants:
        if not merchant:
            return 0.0
        m = merchant.lower()
        if not any(w.lower() in m for w in merchants):
            return 0.0
    return round(amount * float(perk.get("rate", 0)), 2)


# ---------------------------------------------------------------------------
# Net value of a swipe (Module B2)
# ---------------------------------------------------------------------------

@dataclass
class SwipeValue:
    card_id: str
    net_value_inr: float
    points: float
    points_value_inr: float
    surcharge_waiver_inr: float
    txn_fee_inr: float
    milestone_bonus_inr: float
    milestone_note: str | None
    explanation: list[str] = field(default_factory=list)


def transaction_net_value(rules: dict, category: str, amount: float,
                          merchant: str | None = None,
                          cumulative_spend: float = 0.0) -> SwipeValue:
    """net_value = points × point value + surcharge waiver + milestone crossing − txn fees."""
    earn = points_earned(rules, category, amount, merchant)
    pv = float(rules.get("point_value_inr", 0))
    points_value = round(earn.points * pv, 2)
    waiver = surcharge_waiver_value(rules, category, amount, merchant)

    txn_fee = 0.0  # placeholder: per-txn fees (e.g. rent-payment fees) can be added to rules

    bonus_points = milestone_bonus_crossed(rules, cumulative_spend, cumulative_spend + amount)
    bonus_inr = round(bonus_points * pv, 2)
    milestone_note = None
    if bonus_points:
        milestone_note = (f"this spend crosses a milestone → +{bonus_points:g} bonus pts "
                          f"(₹{bonus_inr:g})")

    explanation = []
    if earn.eligible:
        explanation.append(f"{earn.reason} × ₹{pv:g}/pt = ₹{points_value:g}")
    else:
        explanation.append(earn.reason)
    if waiver:
        explanation.append(f"fuel surcharge waiver ≈ ₹{waiver:g}")
    if milestone_note:
        explanation.append(milestone_note)

    net = round(points_value + waiver + bonus_inr - txn_fee, 2)
    return SwipeValue(rules.get("card_id", "?"), net, earn.points, points_value,
                      waiver, txn_fee, bonus_inr, milestone_note, explanation)


def rank_cards_for_spend(cards: list[dict], category: str, amount: float,
                         merchant: str | None = None,
                         cumulative_spend_by_card: dict[str, float] | None = None
                         ) -> list[SwipeValue]:
    """Swipe Advisor: rank a user's cards by net value for one spend."""
    spends = cumulative_spend_by_card or {}
    results = [
        transaction_net_value(rules, category, amount, merchant,
                              spends.get(rules.get("card_id", ""), 0.0))
        for rules in cards
    ]
    return sorted(results, key=lambda r: r.net_value_inr, reverse=True)


# ---------------------------------------------------------------------------
# Milestones (anniversary/period cumulative spend)
# ---------------------------------------------------------------------------

def milestone_bonus_total(rules: dict, cumulative_spend: float) -> float:
    """Total bonus points owed at a cumulative spend level, respecting the cap."""
    ms = rules.get("milestones") or {}
    tiers = sorted(ms.get("tiers") or [], key=lambda t: t["spend"])
    if not tiers:
        return 0.0
    total = 0.0
    last_tier_spend = 0.0
    for tier in tiers:
        if cumulative_spend >= tier["spend"]:
            total += float(tier["bonus_points"])
            last_tier_spend = float(tier["spend"])
    step = ms.get("step_after") or {}
    if step and cumulative_spend > last_tier_spend and last_tier_spend > 0:
        every = float(step["every_spend"])
        per = float(step["bonus_points"])
        total += math.floor((cumulative_spend - last_tier_spend) / every) * per
    cap = ms.get("max_bonus_points")
    if cap is not None:
        total = min(total, float(cap))
    return total


def milestone_bonus_crossed(rules: dict, spend_before: float, spend_after: float) -> float:
    """Bonus points newly unlocked by moving cumulative spend from before -> after."""
    return milestone_bonus_total(rules, spend_after) - milestone_bonus_total(rules, spend_before)


def next_milestone(rules: dict, cumulative_spend: float) -> dict | None:
    """The nearest milestone ahead: how much more spend unlocks how many points."""
    ms = rules.get("milestones") or {}
    tiers = sorted(ms.get("tiers") or [], key=lambda t: t["spend"])
    if not tiers:
        return None
    cap = ms.get("max_bonus_points")
    if cap is not None and milestone_bonus_total(rules, cumulative_spend) >= float(cap):
        return None
    for tier in tiers:
        if cumulative_spend < tier["spend"]:
            return {"at_spend": float(tier["spend"]),
                    "spend_needed": round(float(tier["spend"]) - cumulative_spend, 2),
                    "bonus_points": float(tier["bonus_points"])}
    step = ms.get("step_after") or {}
    if step:
        last = float(tiers[-1]["spend"])
        every = float(step["every_spend"])
        steps_done = math.floor((cumulative_spend - last) / every)
        target = last + (steps_done + 1) * every
        return {"at_spend": target,
                "spend_needed": round(target - cumulative_spend, 2),
                "bonus_points": float(step["bonus_points"])}
    return None


# ---------------------------------------------------------------------------
# Perk unlock gates & annual fee (Module B1 progress tracking)
# ---------------------------------------------------------------------------

def perk_gate_progress(rules: dict, quarter_spend: float, year_spend: float) -> list[dict]:
    """Progress toward spend-gated perks (lounge, BookMyShow) and the fee waiver."""
    out = []
    perks = rules.get("perks") or {}
    for name, perk in perks.items():
        if not isinstance(perk, dict):
            continue
        gate = perk.get("unlock_spend_prev_quarter")
        if gate:
            out.append({
                "perk": name,
                "gate_spend": float(gate),
                "current_spend": quarter_spend,
                "unlocked": quarter_spend >= float(gate),
                "spend_needed": max(0.0, round(float(gate) - quarter_spend, 2)),
                "period": "calendar_quarter",
            })
    waiver = rules.get("annual_fee_waiver_spend") or 0
    if rules.get("annual_fee", 0) and waiver:
        out.append({
            "perk": "annual_fee_waiver",
            "gate_spend": float(waiver),
            "current_spend": year_spend,
            "unlocked": year_spend >= float(waiver),
            "spend_needed": max(0.0, round(float(waiver) - year_spend, 2)),
            "period": "anniversary_year",
            "value_inr": float(rules.get("annual_fee", 0)),
        })
    return out


def effective_annual_fee(rules: dict, year_spend: float) -> float:
    """Annual fee actually payable given the year's spend (0 if waiver met or LTF)."""
    fee = float(rules.get("annual_fee", 0) or 0)
    if fee == 0:
        return 0.0
    waiver = float(rules.get("annual_fee_waiver_spend", 0) or 0)
    if waiver and year_spend >= waiver:
        return 0.0
    if rules.get("annual_fee_gst_extra"):
        fee *= 1.18
    return round(fee, 2)
