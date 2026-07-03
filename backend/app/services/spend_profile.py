"""SpendProfile derivation (input to the Card Recommendation Engine)."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models


def derive_category_spend(db: Session, user_id: int = 1,
                          months: int = 12) -> dict[str, float]:
    """Annualized category → spend map from the user's real transactions."""
    since = date.today() - timedelta(days=months * 30)
    rows = db.execute(
        select(models.Transaction.category_key, models.Transaction.amount)
        .join(models.UserCard, models.Transaction.user_card_id == models.UserCard.id)
        .where(models.UserCard.user_id == user_id,
               models.Transaction.date >= since)).all()
    if not rows:
        return {}
    spend: dict[str, float] = {}
    earliest = db.scalar(
        select(models.Transaction.date)
        .join(models.UserCard, models.Transaction.user_card_id == models.UserCard.id)
        .where(models.UserCard.user_id == user_id)
        .order_by(models.Transaction.date).limit(1))
    observed_days = max((date.today() - max(earliest, since)).days, 30)
    scale = 365 / observed_days
    for category, amount in rows:
        spend[category] = spend.get(category, 0.0) + float(amount)
    return {k: round(v * scale, 2) for k, v in spend.items()}


def save_profile(db: Session, user_id: int, category_spend: dict[str, float],
                 period: str = "trailing_12m_annualized") -> models.SpendProfile:
    profile = models.SpendProfile(
        user_id=user_id, period=period, category_breakdown_json=category_spend,
        monthly_avg=round(sum(category_spend.values()) / 12, 2))
    db.add(profile)
    return profile


def current_primary_card(db: Session, user_id: int = 1) -> str | None:
    """The user's primary card (or first card) — the comparison baseline."""
    cards = db.scalars(select(models.UserCard)
                       .where(models.UserCard.user_id == user_id)
                       .order_by(models.UserCard.is_primary.desc(),
                                 models.UserCard.id)).all()
    return cards[0].card_id if cards else None
