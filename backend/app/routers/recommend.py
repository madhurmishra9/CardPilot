"""Card Recommendation Engine endpoints (Module D, Phase 3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..services import recommend, spend_profile

router = APIRouter(prefix="/api/recommend", tags=["recommend"])

DEFAULT_USER_ID = 1


@router.get("/cards")
def recommend_cards(ltf_only: bool = False, months: int = 12,
                    merchant_share: float = 1.0,
                    db: Session = Depends(get_db)):
    """Rank every catalog card by projected annual net value on the user's
    real spend profile. `ltf_only=true` filters to lifetime-free cards;
    `merchant_share` is the assumed fraction of category spend hitting
    merchant-restricted accelerated rates (1.0 = optimistic)."""
    spend = spend_profile.derive_category_spend(db, DEFAULT_USER_ID, months)
    if not spend:
        return {"spend_profile": {}, "ranked": [],
                "note": "No transactions yet — add or import spends first."}
    spend_profile.save_profile(db, DEFAULT_USER_ID, spend)
    db.commit()

    catalog = {c.card_id: c.rules_json
               for c in db.scalars(select(models.CardCatalog)).all()}
    current = spend_profile.current_primary_card(db, DEFAULT_USER_ID)
    ranked = recommend.rank_cards(catalog, spend, current, ltf_only,
                                  merchant_share=merchant_share)
    return {"spend_profile": spend, "current_card_id": current, "ranked": ranked}


@router.get("/portfolio")
def recommend_portfolio(size: int = 2, ltf_only: bool = False,
                        merchant_share: float = 1.0,
                        db: Session = Depends(get_db)):
    """Best card COMBINATION (2 or 3 cards) with per-category routing —
    the realistic answer, since nobody optimal holds one card."""
    size = max(2, min(size, 3))
    spend = spend_profile.derive_category_spend(db, DEFAULT_USER_ID)
    if not spend:
        return {"portfolios": [],
                "note": "No transactions yet — add or import spends first."}
    catalog = {c.card_id: c.rules_json
               for c in db.scalars(select(models.CardCatalog)).all()}
    return {"spend_profile": spend,
            "portfolios": recommend.rank_portfolios(
                catalog, spend, size=size, ltf_only=ltf_only,
                merchant_share=merchant_share)}
