# session.py — Database engine and session factory
#
# Reads DATABASE_URL from .env:
#   - Not set or empty → sqlite:///maestro.db (local dev)
#   - Set → Postgres connection string (prod / Supabase)
#
# Usage:
#   from maestro.db.session import get_session, init_db
#   init_db()  # Creates tables if they don't exist
#   with get_session() as session:
#       session.add(...)

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

# Load .env from project root
_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env_path)

_DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if not _DATABASE_URL:
    # Default: SQLite in project root
    _db_path = Path(__file__).resolve().parents[2] / "maestro.db"
    _DATABASE_URL = f"sqlite:///{_db_path}"

# SQLite needs check_same_thread=False for FastAPI (multiple threads)
_connect_args = {}
if _DATABASE_URL.startswith("sqlite"):
    _connect_args["check_same_thread"] = False

engine = create_engine(
    _DATABASE_URL,
    connect_args=_connect_args,
    echo=False,  # Set True for SQL debugging
    pool_pre_ping=True,
)

_SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)


def configure(url: str) -> None:
    """Reconfigure the engine (used by tests to inject in-memory SQLite)."""
    global engine, _SessionFactory
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(url, connect_args=connect_args, echo=False, pool_pre_ping=True)
    _SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Provide a transactional session scope.

    Usage:
        with get_session() as session:
            session.add(thing)
            # auto-commits on exit, rolls back on exception
    """
    # Always use the current _SessionFactory (supports reconfiguration)
    factory = _SessionFactory
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
