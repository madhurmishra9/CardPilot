"""Pydantic schema for /data/cards/*.yaml — the guard rail for hand-edited rules.

A non-coder edits YAML; this schema (enforced in CI via tests/test_schema.py)
catches typos, wrong types and missing provenance fields before they can
silently poison the engine's math.
"""

from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RateEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str
    rate_points_per_100: float = Field(ge=0)
    merchants: list[str] = []
    monthly_cap_points: float | None = Field(default=None, ge=0)


class EarnRules(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rates: list[RateEntry]
    excluded_categories: list[str] = []

    @field_validator("rates")
    @classmethod
    def must_have_default(cls, v: list[RateEntry]) -> list[RateEntry]:
        if not any(r.category == "retail_default" for r in v):
            raise ValueError("earn_rules.rates must include a 'retail_default' entry")
        return v


class MilestoneTier(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spend: float = Field(gt=0)
    bonus_points: float = Field(gt=0)


class StepAfter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    every_spend: float = Field(gt=0)
    bonus_points: float = Field(gt=0)


class Milestones(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period: str = "anniversary_year"
    tiers: list[MilestoneTier] = []
    step_after: StepAfter | None = None
    max_bonus_points: float | None = Field(default=None, gt=0)

    @field_validator("period")
    @classmethod
    def known_period(cls, v: str) -> str:
        if v not in ("anniversary_year", "calendar_quarter"):
            raise ValueError(f"unknown milestone period '{v}'")
        return v


class CardRules(BaseModel):
    """Top-level schema for one card file. Extra perk keys are allowed —
    perks are open-ended — but core fields are strictly typed."""

    model_config = ConfigDict(extra="forbid")

    card_id: str
    display_name: str
    issuer: str
    network_variants: list[str] = []
    lifetime_free: bool = False
    joining_fee: float = Field(default=0, ge=0)
    annual_fee: float = Field(default=0, ge=0)
    annual_fee_gst_extra: bool = False
    annual_fee_waiver_spend: float = Field(default=0, ge=0)
    last_verified: date              # provenance is REQUIRED
    source_url: str                  # provenance is REQUIRED
    reward_program: str = ""
    point_value_inr: float = Field(ge=0)
    redemption_fee_inr: float = Field(default=0, ge=0)
    redemption_fee_gst_rate: float = Field(default=0.18, ge=0, le=1)
    points_expiry_months: int = Field(default=0, ge=0)
    earn_rules: EarnRules
    milestones: Milestones = Milestones()
    perks: dict = {}

    @field_validator("card_id")
    @classmethod
    def snake_case_id(cls, v: str) -> str:
        if not re.fullmatch(r"[a-z0-9_]+", v):
            raise ValueError("card_id must be snake_case [a-z0-9_]")
        return v

    @field_validator("source_url")
    @classmethod
    def real_url(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("source_url must be an https:// URL to the issuer's page")
        return v

    @field_validator("milestones", mode="before")
    @classmethod
    def empty_dict_ok(cls, v):
        return v or {}


def months_since_verified(last_verified: str | date, today: date | None = None) -> int:
    today = today or date.today()
    if isinstance(last_verified, str):
        last_verified = date.fromisoformat(last_verified)
    return (today.year - last_verified.year) * 12 + today.month - last_verified.month


STALE_AFTER_MONTHS = 6  # two missed quarterly verification cycles


def is_stale(last_verified: str | date, today: date | None = None) -> bool:
    try:
        return months_since_verified(last_verified, today) >= STALE_AFTER_MONTHS
    except (ValueError, TypeError):
        return True  # unparseable provenance is worse than stale
