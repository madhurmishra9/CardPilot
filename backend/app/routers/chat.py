"""Advisory chat endpoint (Module F, Phase 5)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..services import chat

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    message: str


@router.post("")
def ask(body: ChatMessage, db: Session = Depends(get_db)):
    """Grounded Q&A: engines compute, the LLM (if configured) only explains."""
    return chat.answer(db, body.message)
