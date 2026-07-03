"""Data export — your financial data is never hostage to the app."""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db

router = APIRouter(prefix="/api/export", tags=["export"])

DEFAULT_USER_ID = 1


@router.get("/json")
def export_json(db: Session = Depends(get_db)):
    """Full dump: cards, transactions, redemptions, learned mappings, alerts."""
    user_cards = db.scalars(select(models.UserCard)
                            .where(models.UserCard.user_id == DEFAULT_USER_ID)).all()
    card_ids = [uc.id for uc in user_cards]
    txns = db.scalars(select(models.Transaction)
                      .where(models.Transaction.user_card_id.in_(card_ids))).all()
    events = db.scalars(select(models.RedemptionEvent)
                        .where(models.RedemptionEvent.user_card_id.in_(card_ids))).all()
    learned = db.scalars(select(models.MerchantCategoryMap)
                         .where(models.MerchantCategoryMap.user_id == DEFAULT_USER_ID)).all()
    alerts = db.scalars(select(models.FareAlert)
                        .where(models.FareAlert.user_id == DEFAULT_USER_ID)).all()
    return {
        "cards": [{"id": c.id, "card_id": c.card_id, "variant": c.variant,
                   "last4": c.last4, "statement_day": c.statement_day,
                   "anniversary_month": c.anniversary_month} for c in user_cards],
        "transactions": [{"id": t.id, "user_card_id": t.user_card_id,
                          "date": t.date.isoformat(), "amount": t.amount,
                          "merchant": t.merchant_raw, "category": t.category_key,
                          "points_earned": t.points_earned, "source": t.source}
                         for t in txns],
        "redemption_events": [{"id": e.id, "user_card_id": e.user_card_id,
                               "date": e.date.isoformat(), "points_used": e.points_used,
                               "inr_value_realized": e.inr_value_realized,
                               "fee_paid": e.fee_paid} for e in events],
        "learned_merchant_categories": [{"merchant": m.merchant_norm,
                                         "category": m.category_key} for m in learned],
        "fare_alerts": [{"route": a.route, "target_price": a.target_price,
                         "active": a.active} for a in alerts],
    }


@router.get("/transactions.csv")
def export_transactions_csv(db: Session = Depends(get_db)):
    user_cards = {uc.id: uc for uc in db.scalars(
        select(models.UserCard).where(models.UserCard.user_id == DEFAULT_USER_ID)).all()}
    txns = db.scalars(select(models.Transaction)
                      .where(models.Transaction.user_card_id.in_(list(user_cards)))
                      .order_by(models.Transaction.date)).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["date", "card", "amount_inr", "merchant", "category",
                     "points_earned", "reward_eligible", "source"])
    for t in txns:
        card = user_cards.get(t.user_card_id)
        writer.writerow([t.date.isoformat(), card.card_id if card else "",
                         t.amount, t.merchant_raw, t.category_key,
                         t.points_earned, t.is_reward_eligible, t.source])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cardpilot-transactions.csv"})
