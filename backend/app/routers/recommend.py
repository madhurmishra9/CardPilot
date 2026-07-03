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
                    db: Session = Depends(get_db)):
    """Rank every catalog card by projected annual net value on the user's
    real spend profile. `ltf_only=true` filters to lifetime-free cards."""
    spend = spend_profile.derive_category_spend(db, DEFAULT_USER_ID, months)
    if not spend:
        return {"spend_profile": {}, "ranked": [],
                "note": "No transactions yet — add or import spends first."}
    spend_profile.save_profile(db, DEFAULT_USER_ID, spend)
    db.commit()

    catalog = {c.card_id: c.rules_json
               for c in db.scalars(select(models.CardCatalog)).all()}
    current = spend_profile.current_primary_card(db, DEFAULT_USER_ID)
    ranked = recommend.rank_cards(catalog, spend, current, ltf_only)
    return {"spend_profile": spend, "current_card_id": current, "ranked": ranked}
