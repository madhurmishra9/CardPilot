"""Telegram delivery for nudges — notifications that actually reach you.

Opt-in: set TELEGRAM_BOT_TOKEN (from @BotFather) and TELEGRAM_CHAT_ID (your
chat with the bot). Only nudge TEXT is sent — no card numbers, no balances
beyond what the nudge message itself states.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("cardpilot.telegram")


def configured() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN")
                and os.environ.get("TELEGRAM_CHAT_ID"))


def send(text: str) -> bool:
    """Send one message; failures are logged, never raised — delivery is
    best-effort and must not break the scheduler."""
    if not configured():
        return False
    import httpx
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text},
            timeout=15)
        resp.raise_for_status()
        return True
    except Exception as exc:
        log.warning("telegram send failed: %s", exc)
        return False
