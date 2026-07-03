"""Travel / Flight Savings engine (Module E, Phase 4). Pure functions, zero I/O.

Four angles on flight cost: best card+channel for a booking, points-vs-cash
evaluation, fare-trend timing guidance, and perk-timing nudges (the last is
served by the notifications service using perk_gate_progress).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import redemption as red
from . import rules_engine as eng


def best_card_for_booking(cards: list[dict], fare_inr: float,
                          merchant: str | None = None,
                          cumulative_spend_by_card: dict[str, float] | None = None):
    """Rank the user's cards for a travel booking; effective cost = fare − net value."""
    ranked = eng.rank_cards_for_spend(cards, "travel", fare_inr, merchant,
                                      cumulative_spend_by_card)
    return [{
        "card_id": r.card_id,
        "net_value_inr": r.net_value_inr,
        "effective_cost_inr": round(fare_inr - r.net_value_inr, 2),
        "explanation": r.explanation,
    } for r in ranked]


@dataclass
class PaymentPath:
    path: str                 # cash | points | miles_transfer
    feasible: bool
    effective_cost_inr: float
    value_per_point: float | None
    explanation: str


def points_vs_cash(rules: dict, fare_inr: float, points_balance: float,
                   flight_redemption_options: list[dict] | None = None
                   ) -> list[PaymentPath]:
    """Compare paying cash vs redeeming points for a flight on one card.

    Cash path: pay fare, earn points (net value reduces effective cost).
    Points path: burn points at the best flight-type redemption value, pay the
    per-request fee, and forgo the points' cash-equivalent value elsewhere.
    """
    paths: list[PaymentPath] = []

    cash = eng.transaction_net_value(rules, "travel", fare_inr)
    paths.append(PaymentPath(
        "cash", True, round(fare_inr - cash.net_value_inr, 2), None,
        f"Pay ₹{fare_inr:,.0f}, earn back ₹{cash.net_value_inr:,.2f} in rewards"))

    baseline = float(rules.get("point_value_inr", 0) or 0)
    vpp = baseline
    for opt in flight_redemption_options or []:
        if opt.get("type") in ("flight", "miles_transfer") and opt.get("points_required"):
            vpp = max(vpp, float(opt["inr_value"]) / float(opt["points_required"]))
    if vpp <= 0:
        paths.append(PaymentPath("points", False, fare_inr, None,
                                 "This card's points can't be redeemed for flights"))
        return paths

    points_needed = math.ceil(fare_inr / vpp)
    fee = red.redemption_fee_total(rules)
    feasible = points_balance >= points_needed
    # opportunity cost: those points were worth baseline value as the best alternative
    cost = round(points_needed * baseline + fee, 2)
    paths.append(PaymentPath(
        "points", feasible, cost, round(vpp, 4),
        f"Redeem {points_needed:,} pts at ₹{vpp:.2f}/pt (+₹{fee:g} fee) — "
        + ("you have enough" if feasible
           else f"short {points_needed - points_balance:,.0f} pts")))

    best = min((p for p in paths if p.feasible), key=lambda p: p.effective_cost_inr,
               default=paths[0])
    best.explanation += "  ← cheapest path"
    return paths


@dataclass
class TrendAdvice:
    action: str               # book_now | book_soon | wait | insufficient_history
    latest_fare: float | None
    min_fare: float | None
    avg_fare: float | None
    rationale: str


def fare_trend_advice(fares_chronological: list[float]) -> TrendAdvice:
    """Book-now-vs-wait guidance from stored fare history for a route."""
    fares = [f for f in fares_chronological if f > 0]
    if len(fares) < 3:
        latest = fares[-1] if fares else None
        return TrendAdvice("insufficient_history", latest, min(fares, default=None),
                           None, "Fewer than 3 quotes tracked — check back after a few "
                           "days of history before timing the purchase.")
    latest, lo = fares[-1], min(fares)
    avg = sum(fares) / len(fares)
    half = len(fares) // 2
    rising = (fares[-1] > fares[-2]
              and sum(fares[half:]) / len(fares[half:]) > sum(fares[:half]) / half * 1.03)

    if latest <= lo * 1.02:
        return TrendAdvice("book_now", latest, lo, round(avg, 2),
                           f"Current ₹{latest:,.0f} is at the lowest tracked level "
                           f"(min ₹{lo:,.0f}, avg ₹{avg:,.0f}) — book now.")
    if rising:
        return TrendAdvice("book_soon", latest, lo, round(avg, 2),
                           f"Fares are trending up (now ₹{latest:,.0f} vs avg "
                           f"₹{avg:,.0f}) — book soon.")
    return TrendAdvice("wait", latest, lo, round(avg, 2),
                       f"Current ₹{latest:,.0f} is above the tracked low of "
                       f"₹{lo:,.0f} and not rising — consider waiting.")
