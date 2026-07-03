"""Points ledger (Module B1): DB-facing aggregation over Transactions.

Computes running points, milestone progress and perk-gate progress per user
card by delegating all math to the pure rules engine.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models
from . import rules_engine as eng


def quarter_start(d: date) -> date:
    return date(d.year, 3 * ((d.month - 1) // 3) + 1, 1)


def anniversary_year_start(d: date, anniversary_month: int) -> date:
    year = d.year if d.month >= anniversary_month else d.year - 1
    return date(year, anniversary_month, 1)


def spend_since(db: Session, user_card_id: int, since: date) -> float:
    total = db.scalar(
        select(func.coalesce(func.sum(models.Transaction.amount), 0.0))
        .where(models.Transaction.user_card_id == user_card_id,
               models.Transaction.date >= since))
    return float(total or 0.0)


def points_from_transactions(db: Session, user_card_id: int) -> float:
    total = db.scalar(
        select(func.coalesce(func.sum(models.Transaction.points_earned), 0.0))
        .where(models.Transaction.user_card_id == user_card_id))
    return float(total or 0.0)


def points_redeemed(db: Session, user_card_id: int) -> float:
    total = db.scalar(
        select(func.coalesce(func.sum(models.RedemptionEvent.points_used), 0.0))
        .where(models.RedemptionEvent.user_card_id == user_card_id))
    return float(total or 0.0)


def earn_lots_by_month(db: Session, user_card_id: int) -> list[dict]:
    """Points grouped by earn month — the granularity for expiry alerts."""
    rows = db.execute(
        select(models.Transaction.date, models.Transaction.points_earned)
        .where(models.Transaction.user_card_id == user_card_id,
               models.Transaction.points_earned > 0)).all()
    lots: dict[str, dict] = {}
    for txn_date, points in rows:
        key = f"{txn_date.year}-{txn_date.month:02d}"
        lot = lots.setdefault(key, {"points": 0.0, "earned_on": date(txn_date.year,
                                                                     txn_date.month, 1)})
        lot["points"] += float(points)
    return list(lots.values())


def card_summary(db: Session, user_card: models.UserCard, today: date | None = None) -> dict:
    """Everything the dashboard needs for one card."""
    today = today or date.today()
    rules = user_card.catalog.rules_json
    year_start = anniversary_year_start(today, user_card.anniversary_month)
    q_start = quarter_start(today)

    year_spend = spend_since(db, user_card.id, year_start)
    quarter_spend = spend_since(db, user_card.id, q_start)
    milestone_pts = eng.milestone_bonus_total(rules, year_spend)
    balance = (points_from_transactions(db, user_card.id) + milestone_pts
               - points_redeemed(db, user_card.id))

    return {
        "user_card_id": user_card.id,
        "card_id": user_card.card_id,
        "display_name": user_card.catalog.display_name,
        "points_balance": balance,
        "points_value_inr": round(balance * float(rules.get("point_value_inr", 0)), 2),
        "year_spend": year_spend,
        "quarter_spend": quarter_spend,
        "milestone_bonus_points": milestone_pts,
        "next_milestone": eng.next_milestone(rules, year_spend),
        "perk_gates": eng.perk_gate_progress(rules, quarter_spend, year_spend),
        "effective_annual_fee": eng.effective_annual_fee(rules, year_spend),
    }
