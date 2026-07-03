"""Redemption Advisor endpoints (Module C)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..services import ledger
from ..services import redemption as red

router = APIRouter(prefix="/api/redemption", tags=["redemption"])

DEFAULT_USER_ID = 1


def _user_card(db: Session, user_card_id: int) -> models.UserCard:
    uc = db.get(models.UserCard, user_card_id)
    if not uc or uc.user_id != DEFAULT_USER_ID:
        raise HTTPException(404, "user card not found")
    return uc


def _options(db: Session, card_id: str) -> list[dict]:
    rows = db.scalars(select(models.RedemptionOption)
                      .where(models.RedemptionOption.card_id == card_id)).all()
    return [{"name": o.name, "type": o.type, "points_required": o.points_required,
             "inr_value": o.inr_value, "notes": o.notes} for o in rows]


@router.get("/options/{card_id}")
def list_options(card_id: str, db: Session = Depends(get_db)):
    return _options(db, card_id)


@router.get("/advise/{user_card_id}")
def advise(user_card_id: int, db: Session = Depends(get_db)):
    """Full advisory: balance, ranked options, batching math, expiry, redeem-vs-hold."""
    uc = _user_card(db, user_card_id)
    rules = uc.catalog.rules_json
    balance = (ledger.points_from_transactions(db, uc.id)
               - ledger.points_redeemed(db, uc.id))
    options = _options(db, uc.card_id)
    lots = ledger.earn_lots_by_month(db, uc.id)
    today = date.today()

    decision = red.redeem_vs_hold(rules, options, balance, lots, today)
    return {
        "points_balance": balance,
        "fee_per_request_inr": red.redemption_fee_total(rules),
        "break_even_points": red.break_even_points(rules),
        "batching": asdict(red.batching_advice(rules, balance)) if balance > 0 else None,
        "expiry_alerts": [asdict(a) for a in red.expiry_alerts(rules, lots, today)],
        "ranked_options": [asdict(o) for o in red.rank_options(rules, options, balance)],
        "decision": {"action": decision.action, "rationale": decision.rationale,
                     "best_option": asdict(decision.best_option)
                     if decision.best_option else None},
    }


class LogRedemption(BaseModel):
    user_card_id: int
    points_used: float
    inr_value_realized: float
    fee_paid: float = 0
    date: date
    option_id: int | None = None


@router.post("/events", status_code=201)
def log_redemption(body: LogRedemption, db: Session = Depends(get_db)):
    """Log an actual redemption — this is how CardPilot learns true ₹/point."""
    _user_card(db, body.user_card_id)
    event = models.RedemptionEvent(**body.model_dump())
    db.add(event)
    db.commit()
    realized = round(body.inr_value_realized / body.points_used, 4) if body.points_used else 0
    return {"id": event.id, "realized_value_per_point": realized}
