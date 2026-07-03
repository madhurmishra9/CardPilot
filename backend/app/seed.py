"""Seed the DB from the versioned datasets in /data (idempotent upserts)."""

from __future__ import annotations

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .catalog import REPO_ROOT, load_card_rules, load_categories

REDEMPTIONS_DIR = REPO_ROOT / "data" / "redemptions"


def seed_all(db: Session) -> None:
    seed_user(db)
    seed_catalog(db)
    seed_categories(db)
    seed_redemption_options(db)
    db.commit()


def seed_user(db: Session) -> None:
    if not db.get(models.User, 1):
        db.add(models.User(id=1, name="Local User", prefs_json={}))


def seed_catalog(db: Session) -> None:
    for card_id, rules in load_card_rules().items():
        row = db.get(models.CardCatalog, card_id)
        values = dict(
            display_name=rules.get("display_name", card_id),
            issuer=rules.get("issuer", ""),
            network_variants=rules.get("network_variants", []),
            annual_fee=float(rules.get("annual_fee", 0) or 0),
            annual_fee_waiver_spend=float(rules.get("annual_fee_waiver_spend", 0) or 0),
            rules_json=rules,
            last_verified=str(rules.get("last_verified", "")),
            source_url=rules.get("source_url", ""),
        )
        if row:
            for k, v in values.items():
                setattr(row, k, v)
        else:
            db.add(models.CardCatalog(card_id=card_id, **values))


def seed_categories(db: Session) -> None:
    for cat in load_categories():
        row = db.scalar(select(models.Category)
                        .where(models.Category.key == cat["key"]))
        values = dict(display_name=cat.get("display_name", cat["key"]),
                      mcc_ranges_json=cat.get("mcc_ranges", []),
                      keywords_json=cat.get("keywords", []))
        if row:
            for k, v in values.items():
                setattr(row, k, v)
        else:
            db.add(models.Category(key=cat["key"], **values))


def seed_redemption_options(db: Session) -> None:
    if not REDEMPTIONS_DIR.exists():
        return
    for path in sorted(REDEMPTIONS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        card_id = data["card_id"]
        for opt in data.get("options", []):
            existing = db.scalar(select(models.RedemptionOption).where(
                models.RedemptionOption.card_id == card_id,
                models.RedemptionOption.name == opt["name"]))
            req = float(opt["points_required"])
            values = dict(type=opt.get("type", "voucher"), points_required=req,
                          inr_value=float(opt["inr_value"]),
                          effective_value_per_point=round(float(opt["inr_value"]) / req, 4),
                          notes=opt.get("notes", ""),
                          last_verified=str(opt.get("last_verified", "")))
            if existing:
                for k, v in values.items():
                    setattr(existing, k, v)
            else:
                db.add(models.RedemptionOption(card_id=card_id, name=opt["name"], **values))
