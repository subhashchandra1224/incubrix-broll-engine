"""Database engine, session factory and declarative base.

SQLite is used for the local demo. WAL mode is enabled so the api and worker
processes can share one SQLite file with better concurrent read/write. For
higher concurrency, set DATABASE_URL to a PostgreSQL URL; no other code needs
to change.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()

# SQLite connections are single-thread by default; allow shared use.
_connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)
engine = create_engine(
    settings.database_url,
    echo=settings.db_echo,
    connect_args=_connect_args,
    future=True,
)


if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001
        """Run on every new SQLite connection."""
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")     # better concurrency
        cur.execute("PRAGMA synchronous=NORMAL")    # safe with WAL, faster
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Common declarative base for all ORM models."""
    pass


def get_db():
    """FastAPI dependency: yield a session and close it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create the DB file/dir (for sqlite) and all registered tables.

    Called on app startup. Safe to call repeatedly (create_all is idempotent).
    """
    if settings.database_url.startswith("sqlite"):
        # "sqlite:///./data/broll.db" -> "./data/broll.db"
        db_path = settings.database_url.replace("sqlite:///", "", 1)
        db_dir = os.path.dirname(db_path) or "."
        os.makedirs(db_dir, exist_ok=True)
    # Import the models package so model classes register on Base.metadata.
    # Phase 3 will add the Job model here.
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
