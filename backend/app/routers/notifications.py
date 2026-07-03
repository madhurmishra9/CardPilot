"""Nudges & alerts endpoints (Module G, Phase 5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..services import notifications

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

DEFAULT_USER_ID = 1


@router.get("")
def all_notifications(db: Session = Depends(get_db)):
    """Live nudges (computed now) + stored alerts (from the scheduler)."""
    return {"live": notifications.live_nudges(db, DEFAULT_USER_ID),
            "stored": notifications.stored_notifications(db, DEFAULT_USER_ID)}


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, db: Session = Depends(get_db)):
    n = db.get(models.Notification, notification_id)
    if not n or n.user_id != DEFAULT_USER_ID:
        raise HTTPException(404, "notification not found")
    n.read = True
    db.commit()
    return {"id": n.id, "read": True}
