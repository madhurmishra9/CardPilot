"""Database setup. SQLite local-first by default; set CARDPILOT_DB_URL for Postgres."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DB_URL = os.environ.get("CARDPILOT_DB_URL", "sqlite:///./cardpilot.db")

engine = create_engine(DB_URL, connect_args={"check_same_thread": False}
                       if DB_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
