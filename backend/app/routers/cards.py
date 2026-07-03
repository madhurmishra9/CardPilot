"""Card catalog + the user's wallet."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db

router = APIRouter(prefix="/api/cards", tags=["cards"])

DEFAULT_USER_ID = 1  # local-first, single-user MVP


@router.get("/catalog")
def list_catalog(db: Session = Depends(get_db)):
    cards = db.scalars(select(models.CardCatalog)).all()
    return [{
        "card_id": c.card_id,
        "display_name": c.display_name,
        "issuer": c.issuer,
        "annual_fee": c.annual_fee,
        "annual_fee_waiver_spend": c.annual_fee_waiver_spend,
        "lifetime_free": bool(c.rules_json.get("lifetime_free")),
        "last_verified": c.last_verified,
        "source_url": c.source_url,
    } for c in cards]


@router.get("/catalog/{card_id}")
def get_catalog_card(card_id: str, db: Session = Depends(get_db)):
    card = db.get(models.CardCatalog, card_id)
    if not card:
        raise HTTPException(404, f"unknown card_id {card_id}")
    return {"card_id": card.card_id, "rules": card.rules_json}


class AddUserCard(BaseModel):
    card_id: str
    variant: str = ""
    last4: str = Field("", max_length=4)  # last 4 digits only — never the full PAN
    statement_day: int = 1
    anniversary_month: int = 1
    credit_limit: float = 0
    is_primary: bool = False


@router.get("/mine")
def my_cards(db: Session = Depends(get_db)):
    cards = db.scalars(select(models.UserCard)
                       .where(models.UserCard.user_id == DEFAULT_USER_ID)).all()
    return [{
        "id": c.id, "card_id": c.card_id, "display_name": c.catalog.display_name,
        "variant": c.variant, "last4": c.last4, "is_primary": c.is_primary,
        "anniversary_month": c.anniversary_month,
    } for c in cards]


@router.post("/mine", status_code=201)
def add_card(body: AddUserCard, db: Session = Depends(get_db)):
    if not db.get(models.CardCatalog, body.card_id):
        raise HTTPException(404, f"unknown card_id {body.card_id}")
    card = models.UserCard(user_id=DEFAULT_USER_ID, **body.model_dump())
    db.add(card)
    db.commit()
    return {"id": card.id}


@router.delete("/mine/{user_card_id}", status_code=204)
def remove_card(user_card_id: int, db: Session = Depends(get_db)):
    card = db.get(models.UserCard, user_card_id)
    if not card or card.user_id != DEFAULT_USER_ID:
        raise HTTPException(404, "card not found")
    db.delete(card)
    db.commit()
