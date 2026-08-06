"""SQLModel engine and session (SQLAlchemy) for the scraper's SQLite."""

from __future__ import annotations

import json

from sqlalchemy import event
from sqlmodel import Session, create_engine

from config import DB_PATH

# check_same_thread=False: the app is served in threads/async and creates sessions
# in distinct contexts.
# json_serializer with ensure_ascii=False: preserves readable pt-BR accentuation
# in JSON columns, instead of escaping as \uXXXX.
engine = create_engine(
    f"sqlite:///{DB_PATH}",
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


def get_session():
    """FastAPI dependency: one session per request, closed at the end."""
    with Session(engine) as session:
        yield session
