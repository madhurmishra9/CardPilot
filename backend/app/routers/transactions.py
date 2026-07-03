"""Spend ingestion (Module A): manual entry, CSV/PDF upload, category correction."""

from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..parsers import get_parser
from ..services import categorize as cat
from ..services import rules_engine as eng

router = APIRouter(prefix="/api/transactions", tags=["transactions"])

DEFAULT_USER_ID = 1


def _learned_map(db: Session) -> dict[str, str]:
    rows = db.scalars(select(models.MerchantCategoryMap)
                      .where(models.MerchantCategoryMap.user_id == DEFAULT_USER_ID)).all()
    return {r.merchant_norm: r.category_key for r in rows}


def _categories(db: Session) -> list[dict]:
    return [{"key": c.key, "mcc_ranges": c.mcc_ranges_json, "keywords": c.keywords_json}
            for c in db.scalars(select(models.Category)).all()]


def _insert_txn(db: Session, user_card: models.UserCard, txn_date: date, amount: float,
                merchant: str, category_key: str | None, source: str,
                notes: str = "") -> models.Transaction:
    if category_key is None:
        category_key = cat.categorize(merchant, _categories(db), learned=_learned_map(db))
    rules = user_card.catalog.rules_json
    earn = eng.points_earned(rules, category_key, amount, merchant)
    txn = models.Transaction(
        user_card_id=user_card.id, date=txn_date, amount=amount, merchant_raw=merchant,
        category_key=category_key, is_reward_eligible=earn.eligible,
        points_earned=earn.points, source=source, notes=notes)
    db.add(txn)
    return txn


class ManualTxn(BaseModel):
    user_card_id: int
    date: date
    amount: float
    merchant: str = ""
    category_key: str | None = None  # omit to auto-categorize


@router.post("", status_code=201)
def add_transaction(body: ManualTxn, db: Session = Depends(get_db)):
    user_card = db.get(models.UserCard, body.user_card_id)
    if not user_card:
        raise HTTPException(404, "user card not found")
    txn = _insert_txn(db, user_card, body.date, body.amount, body.merchant,
                      body.category_key, "manual")
    db.commit()
    return {"id": txn.id, "category_key": txn.category_key,
            "points_earned": txn.points_earned,
            "is_reward_eligible": txn.is_reward_eligible}


@router.post("/upload", status_code=201)
async def upload_statement(user_card_id: int = Form(...),
                           parser: str = Form("generic_csv"),
                           mapping: str = Form("{}"),
                           file: UploadFile = File(...),
                           db: Session = Depends(get_db)):
    """Upload a statement (CSV or ICICI PDF). `mapping` is the CSV column-mapping
    wizard output, e.g. {"date": "Txn Date", "amount": "Amount", "merchant": "Details"}."""
    user_card = db.get(models.UserCard, user_card_id)
    if not user_card:
        raise HTTPException(404, "user card not found")
    try:
        parse = get_parser(parser)
    except KeyError as exc:
        raise HTTPException(400, str(exc)) from exc
    content = await file.read()
    try:
        rows = parse(content, json.loads(mapping))
    except (ValueError, KeyError, RuntimeError) as exc:
        raise HTTPException(422, f"parse failed: {exc}") from exc

    source = "pdf" if parser.endswith("pdf") else "csv"
    created = [_insert_txn(db, user_card, r["date"], r["amount"],
                           r.get("merchant_raw", ""), None, source) for r in rows]
    db.commit()
    return {"imported": len(created),
            "points_earned": sum(t.points_earned for t in created)}


@router.get("")
def list_transactions(user_card_id: int | None = None, limit: int = 100,
                      db: Session = Depends(get_db)):
    q = select(models.Transaction).order_by(models.Transaction.date.desc()).limit(limit)
    if user_card_id:
        q = q.where(models.Transaction.user_card_id == user_card_id)
    return [{
        "id": t.id, "user_card_id": t.user_card_id, "date": t.date.isoformat(),
        "amount": t.amount, "merchant": t.merchant_raw, "category_key": t.category_key,
        "points_earned": t.points_earned, "is_reward_eligible": t.is_reward_eligible,
        "source": t.source,
    } for t in db.scalars(q).all()]


class CategoryCorrection(BaseModel):
    category_key: str
    remember: bool = True  # learn merchant -> category for future imports


@router.patch("/{txn_id}/category")
def correct_category(txn_id: int, body: CategoryCorrection, db: Session = Depends(get_db)):
    txn = db.get(models.Transaction, txn_id)
    if not txn:
        raise HTTPException(404, "transaction not found")
    txn.category_key = body.category_key
    rules = txn.card.catalog.rules_json
    earn = eng.points_earned(rules, body.category_key, txn.amount, txn.merchant_raw)
    txn.points_earned, txn.is_reward_eligible = earn.points, earn.eligible

    if body.remember and txn.merchant_raw:
        norm = cat.normalize_merchant(txn.merchant_raw)
        existing = db.scalar(select(models.MerchantCategoryMap).where(
            models.MerchantCategoryMap.user_id == DEFAULT_USER_ID,
            models.MerchantCategoryMap.merchant_norm == norm))
        if existing:
            existing.category_key = body.category_key
        else:
            db.add(models.MerchantCategoryMap(user_id=DEFAULT_USER_ID, merchant_norm=norm,
                                              category_key=body.category_key))
    db.commit()
    return {"id": txn.id, "category_key": txn.category_key,
            "points_earned": txn.points_earned}
