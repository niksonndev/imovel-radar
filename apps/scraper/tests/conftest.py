from __future__ import annotations

from collections.abc import Iterator

import pytest
import shared_models.tables  # noqa: F401  (registra as tabelas no SQLModel.metadata)
from sqlalchemy import text
from sqlalchemy.engine import Engine, make_url
from sqlmodel import Session, SQLModel

import config
from database import make_engine

# Hosts aceitos nos testes: só banco local. A fixture ``session`` recria o schema
# com drop_all/create_all a cada teste, então apontar DATABASE_URL para um banco
# remoto (Neon de produção) APAGA os dados reais. Isso já aconteceu uma vez: uma
# variável de ambiente exportada na sessão do shell sobrepôs o .env local.
LOCAL_DATABASE_HOSTS = {
    None,
    "",
    "localhost",
    "localhost.localdomain",
    "127.0.0.1",
    "::1",
    "host.docker.internal",
    "postgres",
    "db",
}


def _require_local_database(database_url: str) -> None:
    """Aborta a execução se DATABASE_URL não apontar para um banco local."""
    host = make_url(database_url).host
    if host not in LOCAL_DATABASE_HOSTS:
        pytest.exit(
            "DATABASE_URL aponta para um banco REMOTO "
            f"({host or 'host não identificado'}); os testes recriam o schema com "
            "drop_all/create_all e apagariam os dados. Rode com um Postgres local "
            "(ex.: `DATABASE_URL=postgresql+psycopg://postgres:teste123@localhost:5432/imovel_radar`) "
            "ou remova a variável exportada no shell para usar o .env local.",
            returncode=2,
        )


@pytest.fixture(scope="session")
def engine() -> Engine:
    """Engine Postgres compartilhada entre os testes (usa DATABASE_URL)."""
    _require_local_database(config.DATABASE_URL)
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
