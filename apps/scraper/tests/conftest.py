from __future__ import annotations

from collections.abc import Iterator

import pytest
import shared_models.tables  # noqa: F401  (registra as tabelas no SQLModel.metadata)
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel

import config
from database import make_engine


@pytest.fixture(scope="session")
def engine() -> Engine:
    """Engine Postgres compartilhada entre os testes (usa DATABASE_URL)."""
    eng = make_engine(config.DATABASE_URL)
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"Postgres indisponível: {exc}")
    return eng


@pytest.fixture()
def session(engine: Engine) -> Iterator[Session]:
    """Sessão com schema recriado por teste (isolamento entre testes)."""
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
