"""SQLModel engine/session para a Bot Lambda (Postgres/Neon compartilhado)."""

from __future__ import annotations

import json
import logging

from sqlalchemy.engine import Engine
from sqlmodel import create_engine

import config

logger = logging.getLogger(__name__)

_engine: Engine | None = None


def make_engine(database_url: str) -> Engine:
    """Cria engine Postgres com ``pool_pre_ping`` e ``json_serializer``.

    ``pool_pre_ping`` detecta conexões abatidas (Neon pausa o compute por
    inatividade — o wake-up na primeira query é esperado). O serializer
    preserva acentuação pt-BR em colunas JSON.
    """
    if "neon.tech" in database_url and "-pooler" not in database_url:
        logger.warning(
            "DATABASE_URL aponta para Neon sem -pooler; a Lambda deve usar a "
            "connection string pooled."
        )
    return create_engine(
        database_url,
        pool_pre_ping=True,
        json_serializer=lambda obj: json.dumps(obj, ensure_ascii=False),
    )


def get_engine() -> Engine:
    """Engine lazy — evita criar conexão no import (testabilidade)."""
    global _engine
    if _engine is None:
        _engine = make_engine(config.DATABASE_URL)
    return _engine


def reset_engine() -> None:
    """Libera a engine cacheada (testes)."""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None
