"""CardPilot API — local-first credit-card rewards & travel-savings optimizer."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, SessionLocal, engine
from .routers import advisor, cards, redemption, transactions
from .seed import seed_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_all(db)
    yield


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


@app.get("/api/health")
def health():
    return {"status": "ok"}
