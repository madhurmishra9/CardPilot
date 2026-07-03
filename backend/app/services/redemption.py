"""Redemption Advisor engine (Module C). Pure functions, zero I/O.

Answers what/where (rank options by realized value), when (fee amortization,
expiry guard) and redeem-vs-hold. The per-request redemption fee (e.g. ICICI's
₹99+GST) is the single biggest destroyer of value — batching logic lives here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

DEFAULT_GST = 0.18


def redemption_fee_total(rules: dict) -> float:
    """Fee per redemption REQUEST including GST."""
    fee = float(rules.get("redemption_fee_inr", 0) or 0)
    gst = float(rules.get("redemption_fee_gst_rate", DEFAULT_GST) or 0)
    return round(fee * (1 + gst), 2)


def break_even_points(rules: dict, value_per_point: float | None = None) -> float:
    """Points below which a single redemption request loses money to the fee."""
    pv = value_per_point or float(rules.get("point_value_inr", 0) or 0)
    fee = redemption_fee_total(rules)
    if pv <= 0:
        return math.inf
    return math.ceil(fee / pv)


@dataclass
class BatchingAdvice:
    total_points: float
    n_requests: int
    gross_value_inr: float
    total_fees_inr: float
    net_value_inr: float
    warn: bool
    recommendation: str


def batching_advice(rules: dict, total_points: float, n_requests: int = 1,
                    value_per_point: float | None = None) -> BatchingAdvice:
    """Net value of redeeming `total_points` split across `n_requests` requests.

    Warns when splitting (or a tiny redemption) destroys value and recommends
    a single batched request instead.
    """
    pv = value_per_point or float(rules.get("point_value_inr", 0) or 0)
    fee = redemption_fee_total(rules)
    gross = round(total_points * pv, 2)
    fees = round(fee * n_requests, 2)
    net = round(gross - fees, 2)

    single_net = round(gross - fee, 2)
    warn = False
    if n_requests > 1 and fee > 0:
        warn = True
        saved = round(fees - fee, 2)
        rec = (f"Don't split into {n_requests} requests — each costs ₹{fee:g} in fees. "
               f"A single batched request nets ₹{single_net:g} (₹{saved:g} more).")
    elif fee > 0 and gross <= fee:
        warn = True
        be = break_even_points(rules, pv)
        rec = (f"Redeeming {total_points:g} pts (₹{gross:g}) doesn't cover the "
               f"₹{fee:g} per-request fee. Accumulate past ~{be:g} pts break-even "
               f"and batch redemptions.")
    elif fee > 0:
        pct = round(fee / gross * 100, 1)
        rec = (f"One request: ₹{gross:g} gross − ₹{fee:g} fee = ₹{net:g} net "
               f"(fee eats {pct}%). Batch further to dilute the fee.")
    else:
        rec = f"No redemption fee on this card — redeem ₹{gross:g} whenever convenient."
    return BatchingAdvice(total_points, n_requests, gross, fees, net, warn, rec)


# ---------------------------------------------------------------------------
# What / where: rank redemption options by realized value
# ---------------------------------------------------------------------------

@dataclass
class RankedOption:
    name: str
    type: str
    points_required: float
    inr_value: float
    effective_value_per_point: float
    net_value_inr: float
    note: str


def rank_options(rules: dict, options: list[dict], points_available: float) -> list[RankedOption]:
    """Rank affordable redemption options by effective ₹/point AFTER the request fee."""
    fee = redemption_fee_total(rules)
    ranked = []
    for opt in options:
        req = float(opt.get("points_required", 0) or 0)
        if req <= 0 or req > points_available:
            continue
        inr = float(opt.get("inr_value", 0) or 0)
        net = round(inr - fee, 2)
        vpp = round(net / req, 4) if req else 0.0
        note = opt.get("notes") or ""
        if fee:
            note = (note + " " if note else "") + f"(₹{fee:g} request fee already deducted)"
        ranked.append(RankedOption(opt.get("name", "?"), opt.get("type", "?"),
                                   req, inr, vpp, net, note.strip()))
    return sorted(ranked, key=lambda o: o.effective_value_per_point, reverse=True)


# ---------------------------------------------------------------------------
# When: expiry guard
# ---------------------------------------------------------------------------

@dataclass
class ExpiryAlert:
    points: float
    earned_on: date
    expires_on: date
    days_left: int
    value_at_risk_inr: float
    message: str


def _add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    day = min(d.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
                      else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


def expiry_alerts(rules: dict, earn_lots: list[dict], as_of: date,
                  window_days: int = 90) -> list[ExpiryAlert]:
    """Flag point lots expiring within `window_days`.

    earn_lots: [{"points": float, "earned_on": date}, ...]
    """
    months = int(rules.get("points_expiry_months", 0) or 0)
    if months <= 0:  # 0 = never expires
        return []
    pv = float(rules.get("point_value_inr", 0) or 0)
    alerts = []
    for lot in earn_lots:
        earned = lot["earned_on"]
        expires = _add_months(earned, months)
        days_left = (expires - as_of).days
        if 0 <= days_left <= window_days:
            pts = float(lot["points"])
            value = round(pts * pv, 2)
            alerts.append(ExpiryAlert(
                pts, earned, expires, days_left, value,
                f"{pts:g} pts expire on {expires.isoformat()} "
                f"({days_left} days) — redeem before then or lose ₹{value:g}."))
    return sorted(alerts, key=lambda a: a.days_left)


# ---------------------------------------------------------------------------
# Redeem vs hold
# ---------------------------------------------------------------------------

@dataclass
class RedeemDecision:
    action: str          # "redeem" | "hold"
    rationale: list[str]
    best_option: RankedOption | None = None


def redeem_vs_hold(rules: dict, options: list[dict], points_available: float,
                   earn_lots: list[dict] | None = None,
                   as_of: date | None = None,
                   target_value_per_point: float | None = None) -> RedeemDecision:
    """Redeem if best value >= target AND fee-efficient, or expiry forces it; else hold."""
    as_of = as_of or date.today()
    baseline = float(rules.get("point_value_inr", 0) or 0)
    target = target_value_per_point if target_value_per_point is not None else baseline
    rationale: list[str] = []

    alerts = expiry_alerts(rules, earn_lots or [], as_of)
    ranked = rank_options(rules, options, points_available)
    best = ranked[0] if ranked else None

    if alerts:
        at_risk = sum(a.value_at_risk_inr for a in alerts)
        rationale.append(f"₹{at_risk:g} of points expire within 90 days — redeem those first.")
        return RedeemDecision("redeem", rationale, best)

    if best is None:
        rationale.append("No redemption option is affordable at the current balance — hold.")
        return RedeemDecision("hold", rationale, None)

    fee = redemption_fee_total(rules)
    fee_efficient = fee == 0 or (best.points_required * (best.inr_value / best.points_required)
                                 ) >= fee * 10  # fee should eat <=10% of gross
    if best.effective_value_per_point >= target and fee_efficient:
        rationale.append(
            f"Best option '{best.name}' realizes ₹{best.effective_value_per_point:g}/pt "
            f"(≥ target ₹{target:g}/pt) and the fee impact is acceptable — redeem.")
        return RedeemDecision("redeem", rationale, best)

    if not fee_efficient:
        be = break_even_points(rules)
        rationale.append(
            f"The ₹{fee:g} per-request fee eats >10% of this redemption — "
            f"hold and batch (break-even ≈ {be:g} pts).")
    else:
        rationale.append(
            f"Best available ₹{best.effective_value_per_point:g}/pt is below the "
            f"₹{target:g}/pt target — hold for a better option.")
    return RedeemDecision("hold", rationale, best)
