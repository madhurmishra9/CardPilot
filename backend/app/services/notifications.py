"""Nudges & alerts (Module G, Phase 5): computed live from the ledger.

Covers: points expiring ≤90 days, milestone almost reached, fee-waiver
progress, lounge/BMS spend-gate progress. Fare-drop alerts are produced by the
scheduler when it polls active FareAlerts. In-app delivery first (API);
email/Telegram are later delivery channels.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from . import ledger
from . import redemption as red

MILESTONE_NUDGE_WITHIN_INR = 25000  # nudge when a milestone is this close
GATE_NUDGE_WITHIN_INR = 25000


def live_nudges(db: Session, user_id: int = 1, today: date | None = None) -> list[dict]:
    """Compute the current set of nudges across all of the user's cards."""
    today = today or date.today()
    nudges: list[dict] = []
    user_cards = db.scalars(select(models.UserCard)
                            .where(models.UserCard.user_id == user_id)).all()

    for uc in user_cards:
        rules = uc.catalog.rules_json
        name = uc.catalog.display_name
        summary = ledger.card_summary(db, uc, today)

        lots = ledger.earn_lots_by_month(db, uc.id)
        for alert in red.expiry_alerts(rules, lots, today):
            nudges.append({"type": "expiry", "card": name,
                           "message": f"{name}: {alert.message}",
                           "severity": "high" if alert.days_left <= 30 else "medium"})

        nm = summary["next_milestone"]
        if nm and 0 < nm["spend_needed"] <= MILESTONE_NUDGE_WITHIN_INR:
            pv = float(rules.get("point_value_inr", 0) or 0)
            nudges.append({
                "type": "milestone", "card": name, "severity": "medium",
                "message": (f"{name}: spend ₹{nm['spend_needed']:,.0f} more to unlock "
                            f"+{nm['bonus_points']:,.0f} bonus pts "
                            f"(₹{nm['bonus_points'] * pv:,.0f})")})

        for gate in summary["perk_gates"]:
            if gate["unlocked"] or gate["spend_needed"] > GATE_NUDGE_WITHIN_INR:
                continue
            label = gate["perk"].replace("_", " ")
            extra = ""
            if gate["perk"] == "annual_fee_waiver":
                extra = f" and save the ₹{gate.get('value_inr', 0):,.0f} annual fee"
            nudges.append({
                "type": "perk_gate" if gate["perk"] != "annual_fee_waiver" else "fee_waiver",
                "card": name, "severity": "low",
                "message": (f"{name}: ₹{gate['spend_needed']:,.0f} more this "
                            f"{gate['period'].replace('_', ' ')} to unlock {label}{extra}")})

    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(nudges, key=lambda n: order.get(n["severity"], 3))


def stored_notifications(db: Session, user_id: int = 1, limit: int = 50) -> list[dict]:
    rows = db.scalars(select(models.Notification)
                      .where(models.Notification.user_id == user_id)
                      .order_by(models.Notification.created_at.desc())
                      .limit(limit)).all()
    return [{"id": n.id, "type": n.type, "message": n.message, "read": n.read,
             "created_at": n.created_at.isoformat()} for n in rows]
