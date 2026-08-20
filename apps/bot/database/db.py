"""SQLModel engine/session para a Bot Lambda (Postgres/Neon compartilhado)."""

from __future__ import annotations

import json

from sqlalchemy.engine import Engine
from sqlmodel import create_engine

import config


def make_engine(database_url: str) -> Engine:
    """Cria engine Postgres com ``pool_pre_ping`` e ``json_serializer``.

    ``pool_pre_ping`` detecta conexões abatidas (Neon pausa o compute por
    inatividade — o wake-up na primeira query é esperado). O serializer
    preserva acentuação pt-BR em colunas JSON.
    """
    return create_engine(
        database_url,
        pool_pre_ping=True,
        json_serializer=lambda obj: json.dumps(obj, ensure_ascii=False),
    )


engine = make_engine(config.DATABASE_URL)
