"""SQLModel engine and session (SQLAlchemy) for the scraper's SQLite."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from config import DB_PATH


def make_engine(db_path: Path | str) -> Engine:
    """Cria engine com PRAGMAs e json_serializer configurados.

    check_same_thread=False: app servida em threads/async, sessions
    criadas em contextos distintos.
    json_serializer com ensure_ascii=False: preserva acentuação pt-BR
    legível em colunas JSON, em vez de escapar como \\uXXXX.
    """
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        json_serializer=lambda obj: json.dumps(obj, ensure_ascii=False),
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ARG001
        """Enables FK enforcement per connection (equivalent to the original PRAGMA)."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


engine = make_engine(DB_PATH)


def get_session():
    """FastAPI dependency: one session per request, closed at the end."""
    with Session(engine) as session:
        yield session
