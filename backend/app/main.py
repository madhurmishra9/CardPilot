"""CardPilot API — local-first credit-card rewards & travel-savings optimizer."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, SessionLocal, engine
from .routers import (advisor, cards, chat, notifications, recommend,
                      redemption, transactions, travel)
from .seed import seed_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_all(db)
    scheduler = None
    if os.environ.get("CARDPILOT_ENABLE_SCHEDULER") == "1":
        from .scheduler import start_scheduler
        scheduler = start_scheduler()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="CardPilot", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cards.router)
app.include_router(transactions.router)
app.include_router(advisor.router)
app.include_router(redemption.router)
app.include_router(recommend.router)
app.include_router(travel.router)
app.include_router(chat.router)
app.include_router(notifications.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
