"""SQLAlchemy models — data model from spec §3.

Sensitive-data rule: never store full PANs; UserCard keeps last-4 digits only.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey,
                        Integer, String, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    prefs_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class CardCatalog(Base):
    __tablename__ = "card_catalog"
    card_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(160))
    issuer: Mapped[str] = mapped_column(String(120), default="")
    network_variants: Mapped[list] = mapped_column(JSON, default=list)
    annual_fee: Mapped[float] = mapped_column(Float, default=0)
    annual_fee_waiver_spend: Mapped[float] = mapped_column(Float, default=0)
    rules_json: Mapped[dict] = mapped_column(JSON)          # full YAML-equivalent
    last_verified: Mapped[str] = mapped_column(String(16), default="")
    source_url: Mapped[str] = mapped_column(String(400), default="")


class UserCard(Base):
    __tablename__ = "user_cards"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    card_id: Mapped[str] = mapped_column(ForeignKey("card_catalog.card_id"))
    variant: Mapped[str] = mapped_column(String(24), default="")
    last4: Mapped[str] = mapped_column(String(4), default="")   # NEVER the full PAN
    statement_day: Mapped[int] = mapped_column(Integer, default=1)
    anniversary_month: Mapped[int] = mapped_column(Integer, default=1)
    credit_limit: Mapped[float] = mapped_column(Float, default=0)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    catalog: Mapped[CardCatalog] = relationship()


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(48), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    mcc_ranges_json: Mapped[list] = mapped_column(JSON, default=list)
    keywords_json: Mapped[list] = mapped_column(JSON, default=list)


class MerchantCategoryMap(Base):
    """Learned merchant -> category mapping (user corrected once, remembered)."""
    __tablename__ = "merchant_category_map"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    merchant_norm: Mapped[str] = mapped_column(String(200), index=True)
    category_key: Mapped[str] = mapped_column(String(48))


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_card_id: Mapped[int] = mapped_column(ForeignKey("user_cards.id"))
    date: Mapped[date] = mapped_column(Date)
    amount: Mapped[float] = mapped_column(Float)
    merchant_raw: Mapped[str] = mapped_column(String(240), default="")
    category_key: Mapped[str] = mapped_column(String(48), default="retail_default")
    is_reward_eligible: Mapped[bool] = mapped_column(Boolean, default=True)
    points_earned: Mapped[float] = mapped_column(Float, default=0)
    source: Mapped[str] = mapped_column(String(12), default="manual")  # manual|csv|pdf|aa
    notes: Mapped[str] = mapped_column(Text, default="")

    card: Mapped[UserCard] = relationship()


class PointsBalance(Base):
    __tablename__ = "points_balances"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_card_id: Mapped[int] = mapped_column(ForeignKey("user_cards.id"))
    program: Mapped[str] = mapped_column(String(120), default="")
    balance: Mapped[float] = mapped_column(Float, default=0)
    as_of_date: Mapped[date] = mapped_column(Date)
    expiring_soon_json: Mapped[list] = mapped_column(JSON, default=list)


class RedemptionOption(Base):
    __tablename__ = "redemption_options"
    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("card_catalog.card_id"))
    name: Mapped[str] = mapped_column(String(160))
    type: Mapped[str] = mapped_column(String(24))  # voucher|flight|cashback|product|miles_transfer
    points_required: Mapped[float] = mapped_column(Float)
    inr_value: Mapped[float] = mapped_column(Float)
    effective_value_per_point: Mapped[float] = mapped_column(Float)
    notes: Mapped[str] = mapped_column(Text, default="")
    last_verified: Mapped[str] = mapped_column(String(16), default="")


class RedemptionEvent(Base):
    """User-logged actual redemptions — learns true realized ₹/point over time."""
    __tablename__ = "redemption_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_card_id: Mapped[int] = mapped_column(ForeignKey("user_cards.id"))
    option_id: Mapped[int | None] = mapped_column(ForeignKey("redemption_options.id"),
                                                  nullable=True)
    points_used: Mapped[float] = mapped_column(Float)
    inr_value_realized: Mapped[float] = mapped_column(Float)
    fee_paid: Mapped[float] = mapped_column(Float, default=0)
    date: Mapped[date] = mapped_column(Date)


class SpendProfile(Base):
    __tablename__ = "spend_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    period: Mapped[str] = mapped_column(String(24))  # e.g. "2026-H1", "trailing_12m"
    category_breakdown_json: Mapped[dict] = mapped_column(JSON, default=dict)
    monthly_avg: Mapped[float] = mapped_column(Float, default=0)
    derived_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class FareQuote(Base):
    """Phase 4: fare history per route (schema ready; provider integration later)."""
    __tablename__ = "fare_quotes"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    origin: Mapped[str] = mapped_column(String(8))
    dest: Mapped[str] = mapped_column(String(8))
    depart_date: Mapped[date] = mapped_column(Date)
    return_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cabin: Mapped[str] = mapped_column(String(16), default="economy")
    cheapest_fare: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(48), default="")
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class FareAlert(Base):
    __tablename__ = "fare_alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    route: Mapped[str] = mapped_column(String(20))  # "BOM-BKK"
    target_price: Mapped[float] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_notified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(16))  # swipe|switch_card|redeem|travel
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    rationale: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
