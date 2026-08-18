"""SQLModel engine and session (SQLAlchemy) for the scraper's Postgres."""

from __future__ import annotations

import json

from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

import config


def make_engine(database_url: str) -> Engine:
    """Cria engine Postgres com ``pool_pre_ping`` e ``json_serializer``.

    ``pool_pre_ping=True``: detecta conexões ociosas/abatidas antes de usar
    (importante em ambientes serverless/Neon, onde conexões podem ser cortadas).
    ``json_serializer`` com ``ensure_ascii=False``: preserva a acentuação pt-BR
    em colunas JSON, sem escapar para sequências unicode.
    """
    return create_engine(
        database_url,
        pool_pre_ping=True,
        json_serializer=lambda obj: json.dumps(obj, ensure_ascii=False),
    )


engine = make_engine(config.DATABASE_URL)


def get_session():
    """FastAPI dependency: one session per request, closed at the end."""
    with Session(engine) as session:
        yield session
