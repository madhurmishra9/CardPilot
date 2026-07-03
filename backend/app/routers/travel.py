"""Travel Savings endpoints (Module E, Phase 4)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..providers.fare_provider import get_fare_provider
from ..services import ledger, travel

router = APIRouter(prefix="/api/travel", tags=["travel"])

DEFAULT_USER_ID = 1


class FareSearch(BaseModel):
    origin: str
    dest: str
    depart_date: date
    return_date: date | None = None
    cabin: str = "economy"


@router.post("/search")
def search_fares(body: FareSearch, db: Session = Depends(get_db)):
    """Search fares, store the quote history, and return the full advisory:
    trend timing, best card for the booking, and points-vs-cash per card."""
    provider = get_fare_provider()
    try:
        fares = provider.search(body.origin, body.dest, body.depart_date,
                                body.return_date, body.cabin)
    except NotImplementedError as exc:
        raise HTTPException(501, str(exc)) from exc
    if not fares:
        return {"fares": [], "note": "no fares found"}

    cheapest = fares[0]
    db.add(models.FareQuote(
        user_id=DEFAULT_USER_ID, origin=cheapest.origin, dest=cheapest.dest,
        depart_date=cheapest.depart_date, return_date=cheapest.return_date,
        cabin=cheapest.cabin, cheapest_fare=cheapest.price_inr, source=cheapest.source))
    db.commit()

    history = db.scalars(
        select(models.FareQuote)
        .where(models.FareQuote.user_id == DEFAULT_USER_ID,
               models.FareQuote.origin == cheapest.origin,
               models.FareQuote.dest == cheapest.dest)
        .order_by(models.FareQuote.checked_at)).all()
    trend = travel.fare_trend_advice([q.cheapest_fare for q in history])

    user_cards = db.scalars(select(models.UserCard)
                            .where(models.UserCard.user_id == DEFAULT_USER_ID)).all()
    best_cards = travel.best_card_for_booking(
        [uc.catalog.rules_json for uc in user_cards], cheapest.price_inr)
    names = {uc.card_id: uc.catalog.display_name for uc in user_cards}
    for row in best_cards:
        row["display_name"] = names.get(row["card_id"], row["card_id"])

    paths = {}
    for uc in user_cards:
        balance = (ledger.points_from_transactions(db, uc.id)
                   - ledger.points_redeemed(db, uc.id))
        options = [{"type": o.type, "points_required": o.points_required,
                    "inr_value": o.inr_value}
                   for o in db.scalars(select(models.RedemptionOption).where(
                       models.RedemptionOption.card_id == uc.card_id)).all()]
        paths[uc.catalog.display_name] = [
            asdict(p) for p in travel.points_vs_cash(uc.catalog.rules_json,
                                                     cheapest.price_inr, balance, options)]

    return {
        "fares": [asdict(f) for f in fares],
        "trend": asdict(trend),
        "best_card": best_cards,
        "points_vs_cash": paths,
    }


class AlertBody(BaseModel):
    route: str          # "BOM-BKK"
    target_price: float


@router.post("/alerts", status_code=201)
def create_alert(body: AlertBody, db: Session = Depends(get_db)):
    if "-" not in body.route:
        raise HTTPException(422, "route must look like 'BOM-BKK'")
    alert = models.FareAlert(user_id=DEFAULT_USER_ID, route=body.route.upper(),
                             target_price=body.target_price, active=True)
    db.add(alert)
    db.commit()
    return {"id": alert.id}


@router.get("/alerts")
def list_alerts(db: Session = Depends(get_db)):
    alerts = db.scalars(select(models.FareAlert)
                        .where(models.FareAlert.user_id == DEFAULT_USER_ID)).all()
    return [{"id": a.id, "route": a.route, "target_price": a.target_price,
             "active": a.active,
             "last_notified": a.last_notified.isoformat() if a.last_notified else None}
            for a in alerts]


@router.delete("/alerts/{alert_id}", status_code=204)
def delete_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(models.FareAlert, alert_id)
    if not alert or alert.user_id != DEFAULT_USER_ID:
        raise HTTPException(404, "alert not found")
    db.delete(alert)
    db.commit()


@router.get("/quotes")
def quote_history(origin: str, dest: str, db: Session = Depends(get_db)):
    quotes = db.scalars(
        select(models.FareQuote)
        .where(models.FareQuote.user_id == DEFAULT_USER_ID,
               models.FareQuote.origin == origin.upper(),
               models.FareQuote.dest == dest.upper())
        .order_by(models.FareQuote.checked_at)).all()
    return [{"fare": q.cheapest_fare, "checked_at": q.checked_at.isoformat(),
             "source": q.source} for q in quotes]
