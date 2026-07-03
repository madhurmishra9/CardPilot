"""Advisory chat (Module F, Phase 5).

Deterministic intent routing + engine tool calls produce the FACTS; the LLM
provider (if any) only rephrases them. The model never computes reward math —
that is the grounding contract from the spec.
"""

from __future__ import annotations

import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..providers.llm_provider import get_llm_provider
from . import ledger, notifications
from . import redemption as red
from . import rules_engine as eng

AMOUNT_RE = re.compile(r"(?:₹|rs\.?\s*|inr\s*)?([\d,]+(?:\.\d+)?)\s*(k|l|lakh)?", re.I)

CATEGORY_HINTS = {
    "groceries": ["grocer", "bigbasket", "dmart", "supermarket"],
    "dining": ["dinner", "restaurant", "swiggy", "zomato", "food", "dining", "lunch"],
    "fuel": ["fuel", "petrol", "diesel", "hpcl", "bpcl"],
    "utilities": ["electricity", "utility", "bill", "recharge", "broadband"],
    "insurance": ["insurance", "premium", "lic"],
    "travel": ["flight", "fly", "air", "hotel", "trip", "travel", "train"],
    "online_shopping": ["amazon", "flipkart", "online", "myntra", "shopping"],
    "entertainment": ["movie", "bookmyshow", "netflix"],
}


def _extract_amount(text: str) -> float | None:
    best = None
    for m in AMOUNT_RE.finditer(text):
        value = float(m.group(1).replace(",", ""))
        unit = (m.group(2) or "").lower()
        if unit == "k":
            value *= 1_000
        elif unit in ("l", "lakh"):
            value *= 100_000
        if value >= 10 and (best is None or value > best):
            best = value
    return best


def _extract_category(text: str) -> str:
    lower = text.lower()
    for cat, hints in CATEGORY_HINTS.items():
        if any(h in lower for h in hints):
            return cat
    return "retail_default"


def route_intent(text: str) -> str:
    lower = text.lower()
    if any(w in lower for w in ("redeem", "redemption", "points worth", "expire")):
        return "redeem"
    if any(w in lower for w in ("lounge", "milestone", "waiver", "progress", "unlock",
                                "how close")):
        return "progress"
    if any(w in lower for w in ("better card", "switch", "compare card", "recommend",
                                "new card", "which card should i get")):
        return "recommend"
    if any(w in lower for w in ("which card", "swipe", "use for", "pay with", "best card")):
        return "swipe"
    return "help"


def _facts_swipe(db: Session, text: str) -> str:
    amount = _extract_amount(text) or 1000
    category = _extract_category(text)
    user_cards = db.scalars(select(models.UserCard)
                            .where(models.UserCard.user_id == 1)).all()
    if not user_cards:
        return "You haven't added any cards yet — add one in the My Cards tab."
    ranked = eng.rank_cards_for_spend([uc.catalog.rules_json for uc in user_cards],
                                      category, amount)
    names = {uc.card_id: uc.catalog.display_name for uc in user_cards}
    lines = [f"For ₹{amount:,.0f} on {category.replace('_', ' ')}:"]
    for i, r in enumerate(ranked[:3]):
        lines.append(f"{i + 1}. {names.get(r.card_id, r.card_id)} — net ₹{r.net_value_inr:g}"
                     f" ({'; '.join(r.explanation)})")
    return "\n".join(lines)


def _facts_redeem(db: Session, today: date) -> str:
    user_cards = db.scalars(select(models.UserCard)
                            .where(models.UserCard.user_id == 1)).all()
    if not user_cards:
        return "You haven't added any cards yet."
    lines = []
    for uc in user_cards:
        rules = uc.catalog.rules_json
        balance = (ledger.points_from_transactions(db, uc.id)
                   - ledger.points_redeemed(db, uc.id))
        if balance <= 0:
            continue
        options = [{"name": o.name, "type": o.type, "points_required": o.points_required,
                    "inr_value": o.inr_value}
                   for o in db.scalars(select(models.RedemptionOption).where(
                       models.RedemptionOption.card_id == uc.card_id)).all()]
        lots = ledger.earn_lots_by_month(db, uc.id)
        decision = red.redeem_vs_hold(rules, options, balance, lots, today)
        lines.append(f"{uc.catalog.display_name}: {balance:,.0f} pts. "
                     f"Advice: {decision.action.upper()} — {' '.join(decision.rationale)}")
    return "\n".join(lines) or "No points balance on any card yet."


def _facts_progress(db: Session, today: date) -> str:
    nudges = notifications.live_nudges(db, 1, today)
    if not nudges:
        return "No pending milestones or perk gates right now — you're all caught up."
    return "\n".join(f"• {n['message']}" for n in nudges[:6])


def _facts_recommend(db: Session) -> str:
    from . import recommend  # local import: avoids cycle at module load
    from .spend_profile import current_primary_card, derive_category_spend
    catalog = {c.card_id: c.rules_json
               for c in db.scalars(select(models.CardCatalog)).all()}
    spend = derive_category_spend(db, 1)
    if not spend:
        return "I need some transactions first — add or import spends, then ask again."
    current = current_primary_card(db, 1)
    ranked = recommend.rank_cards(catalog, spend, current)[:3]
    lines = ["Top cards for your actual spend profile (projected annual net value):"]
    for i, r in enumerate(ranked):
        delta = (f", {r['delta_vs_current_inr']:+,.0f} vs your current card"
                 if "delta_vs_current_inr" in r and not r["is_current"] else "")
        lines.append(f"{i + 1}. {r['display_name']} — ₹{r['annual_net_value']:,.0f}/yr"
                     f" ({r['charges_flag']}{delta})")
    return "\n".join(lines)


HELP = ("I can answer: 'Which card for ₹5k groceries?', 'Should I redeem my points?', "
        "'How close am I to the lounge benefit?', or 'Is there a better card for me?'. "
        "All numbers come from the deterministic engines, never from a model's memory.")


def answer(db: Session, message: str, today: date | None = None) -> dict:
    """Route the question, compute grounded facts, optionally rephrase via LLM."""
    today = today or date.today()
    intent = route_intent(message)
    if intent == "swipe":
        facts = _facts_swipe(db, message)
    elif intent == "redeem":
        facts = _facts_redeem(db, today)
    elif intent == "progress":
        facts = _facts_progress(db, today)
    elif intent == "recommend":
        facts = _facts_recommend(db)
    else:
        facts = HELP
    provider = get_llm_provider()
    return {"intent": intent, "facts": facts,
            "reply": provider.explain(message, facts), "llm": provider.name}
