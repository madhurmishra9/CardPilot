"""CardPilot API — local-first credit-card rewards & travel-savings optimizer.

Single-server mode: when `frontend/dist` exists (npm run build), this app also
serves the SPA, so one `uvicorn` process is the whole product — the setup used
for phones (see docs/ANDROID.md) and any non-dev deployment.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .catalog import REPO_ROOT
from .db import Base, SessionLocal, engine
from .routers import (
    advisor,
    cards,
    chat,
    export,
    notifications,
    recommend,
    redemption,
    transactions,
    travel,
)
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
app.include_router(export.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"),
              name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        """SPA fallback: real files (sw.js, manifest, icon) are served as-is,
        every other non-API path gets index.html so client routing works."""
        if full_path.startswith("api/"):
            raise HTTPException(404)
        candidate = (FRONTEND_DIST / full_path).resolve()
        if (full_path and candidate.is_file()
                and candidate.is_relative_to(FRONTEND_DIST)):
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
