"""APScheduler jobs (spec §4-E): daily fare-alert polls + expiry/milestone scans.

Off by default so tests and one-shot scripts stay deterministic; enable with
CARDPILOT_ENABLE_SCHEDULER=1 when running the server for real.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime

from sqlalchemy import select

from . import models
from .db import SessionLocal
from .providers import telegram
from .providers.fare_provider import get_fare_provider
from .services import notifications

log = logging.getLogger("cardpilot.scheduler")


def _notify(db, user_id: int, type_: str, message: str, payload: dict | None = None):
    """Persist a notification and push it to Telegram if configured."""
    db.add(models.Notification(user_id=user_id, type=type_, message=message,
                               payload_json=payload or {}))
    telegram.send(f"CardPilot · {message}")


def poll_fare_alerts() -> int:
    """Check each active FareAlert against a fresh quote; notify on target hit."""
    provider = get_fare_provider()
    fired = 0
    with SessionLocal() as db:
        alerts = db.scalars(select(models.FareAlert)
                            .where(models.FareAlert.active)).all()
        for alert in alerts:
            try:
                origin, dest = alert.route.split("-", 1)
                fares = provider.search(origin, dest, date.today())
            except Exception as exc:  # provider down ≠ app down
                log.warning("fare poll failed for %s: %s", alert.route, exc)
                continue
            if not fares:
                continue
            cheapest = fares[0]
            db.add(models.FareQuote(
                user_id=alert.user_id, origin=cheapest.origin, dest=cheapest.dest,
                depart_date=cheapest.depart_date, return_date=cheapest.return_date,
                cabin=cheapest.cabin, cheapest_fare=cheapest.price_inr,
                source=cheapest.source))
            if cheapest.price_inr <= alert.target_price:
                _notify(db, alert.user_id, "fare_drop",
                        f"Fare drop: {alert.route} at ₹{cheapest.price_inr:,.0f} "
                        f"({cheapest.carrier}) — at/below your "
                        f"₹{alert.target_price:,.0f} target.",
                        {"route": alert.route, "fare": cheapest.price_inr})
                alert.last_notified = datetime.now(UTC)
                fired += 1
        db.commit()
    return fired


def scan_nudges() -> int:
    """Persist high/medium live nudges (expiry, milestones) as notifications."""
    stored = 0
    with SessionLocal() as db:
        for nudge in notifications.live_nudges(db):
            if nudge["severity"] == "low":
                continue
            exists = db.scalar(select(models.Notification).where(
                models.Notification.message == nudge["message"],
                models.Notification.read == False))  # noqa: E712
            if exists:
                continue
            _notify(db, 1, nudge["type"], nudge["message"], nudge)
            stored += 1
        db.commit()
    return stored


def statement_day_reminders() -> int:
    """On each card's statement day, remind the user to upload the statement —
    ingestion friction is what kills personal-finance tools."""
    today = date.today()
    sent = 0
    with SessionLocal() as db:
        cards = db.scalars(select(models.UserCard)).all()
        for uc in cards:
            if uc.statement_day != today.day:
                continue
            message = (f"{uc.catalog.display_name}: statement day — upload this "
                       f"month's statement to keep advice accurate.")
            exists = db.scalar(select(models.Notification).where(
                models.Notification.message == message,
                models.Notification.read == False))  # noqa: E712
            if exists:
                continue
            _notify(db, uc.user_id, "statement_day", message)
            sent += 1
        db.commit()
    return sent


def start_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(poll_fare_alerts, "cron", hour=8, id="fare_alerts")
    scheduler.add_job(scan_nudges, "cron", hour=9, id="nudge_scan")
    scheduler.add_job(statement_day_reminders, "cron", hour=10, id="statement_day")
    scheduler.start()
    log.info("scheduler started: fare polls (08:00), nudge scans (09:00), "
             "statement-day reminders (10:00) IST")
    return scheduler
