"""Database setup. SQLite local-first by default; set CARDPILOT_DB_URL for Postgres.

Encryption at rest (opt-in): set CARDPILOT_DB_KEY and install sqlcipher3
(`pip install sqlcipher3-binary`) — the SQLite file is then SQLCipher-encrypted.
Without the driver the app refuses to silently run unencrypted when a key was
requested, so a config mistake can't leak plaintext.
"""

from __future__ import annotations

import logging
import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

log = logging.getLogger("cardpilot.db")

DB_URL = os.environ.get("CARDPILOT_DB_URL", "sqlite:///./cardpilot.db")
DB_KEY = os.environ.get("CARDPILOT_DB_KEY", "")


def _make_engine():
    connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
    if DB_KEY and DB_URL.startswith("sqlite"):
        try:
            import sqlcipher3  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "CARDPILOT_DB_KEY is set but sqlcipher3 is not installed — "
                "run `pip install sqlcipher3-binary` (refusing to run "
                "unencrypted when encryption was requested)") from exc
        import sqlcipher3
        eng = create_engine(DB_URL, connect_args=connect_args,
                            module=sqlcipher3.dbapi2)

        @event.listens_for(eng, "connect")
        def _set_key(dbapi_conn, _record):
            dbapi_conn.execute(f"PRAGMA key = '{DB_KEY.replace(chr(39), chr(39) * 2)}'")

        log.info("SQLCipher encryption at rest: ENABLED")
        return eng
    if DB_URL.startswith("sqlite"):
        log.info("DB encryption at rest: disabled (set CARDPILOT_DB_KEY to enable)")
    return create_engine(DB_URL, connect_args=connect_args)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
