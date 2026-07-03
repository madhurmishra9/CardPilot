"""Swipe Advisor (Module B2): which card to swipe for a given spend."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..services import ledger
from ..services import rules_engine as eng

router = APIRouter(prefix="/api/advisor", tags=["advisor"])

DEFAULT_USER_ID = 1


class SwipeQuery(BaseModel):
    category: str
    amount: float
    merchant: str | None = None


@router.post("/swipe")
def swipe_advisor(body: SwipeQuery, db: Session = Depends(get_db)):
    """Rank the user's cards by net value for this spend, math included."""
    user_cards = db.scalars(select(models.UserCard)
                            .where(models.UserCard.user_id == DEFAULT_USER_ID)).all()
    today = date.today()
    rules_list, spends, names = [], {}, {}
    for uc in user_cards:
        rules = uc.catalog.rules_json
        rules_list.append(rules)
        year_start = ledger.anniversary_year_start(today, uc.anniversary_month)
        spends[uc.card_id] = ledger.spend_since(db, uc.id, year_start)
        names[uc.card_id] = uc.catalog.display_name

    ranked = eng.rank_cards_for_spend(rules_list, body.category, body.amount,
                                      body.merchant, spends)
    return [{**asdict(r), "display_name": names.get(r.card_id, r.card_id)}
            for r in ranked]


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    """Per-card summary: balance, milestone & perk-gate progress, fee status."""
    user_cards = db.scalars(select(models.UserCard)
                            .where(models.UserCard.user_id == DEFAULT_USER_ID)).all()
    return [ledger.card_summary(db, uc) for uc in user_cards]
