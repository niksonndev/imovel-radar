"""Camada de dados da Bot Lambda — acesso direto ao Postgres compartilhado (ADR 0005).

Lê/escreve no Postgres via SQLModel usando os table models de
``shared_models.tables``, que os handlers consomem diretamente (ver
``docs/bot-models-migration.md``). A bot é dona de
``users``/``alerts``/``alert_matches`` e lê ``listing``.
"""

from __future__ import annotations

import logging

from shared_models.tables import Alert, ListingAlertMatch
from sqlmodel import Session

from database import queries
from database.db import get_engine

logger = logging.getLogger(__name__)


# ── Users (dona: bot) ──────────────────────────────────────────────────────
async def ensure_user(chat_id: int) -> bool:
    """Garante a existência do usuário; cria se necessário (idempotente)."""
    try:
        with Session(get_engine()) as session:
            queries.ensure_user(session, chat_id)
            session.commit()
        return True
    except Exception:
        logger.exception("Falha ao garantir usuário %s", chat_id)
        return False


# ── Listings / bairros (read-only) ─────────────────────────────────────────
async def get_neighbourhoods() -> list[str]:
    with Session(get_engine()) as session:
        return queries.get_neighbourhoods(session)


# ── Alerts (dona: bot) ─────────────────────────────────────────────────────
async def create_alert(
    *,
    chat_id: int,
    alert_name: str,
    min_price: int | None = None,
    max_price: int | None = None,
    neighbourhoods: list[str],
) -> int:
    """Cria o alerta no Postgres e retorna o id gerado (idempotente nos filtros)."""
    if min_price is None and max_price is None:
        raise ValueError("Informe min_price, max_price, ou ambos.")
    with Session(get_engine()) as session:
        existing = queries.find_equivalent_alert(
            session,
            chat_id=chat_id,
            alert_name=alert_name,
            min_price=min_price,
            max_price=max_price,
            neighbourhoods=neighbourhoods,
        )
        if existing is not None and existing.id is not None:
            return existing.id
        alert_id = queries.create_alert(
            session,
            chat_id=chat_id,
            alert_name=alert_name,
            min_price=min_price,
            max_price=max_price,
            neighbourhoods=neighbourhoods,
        )
        session.commit()
    return alert_id


async def get_alerts_for_user(chat_id: int) -> list[Alert]:
    with Session(get_engine()) as session:
        return list(queries.get_alerts_for_user(session, chat_id))


async def get_active_alerts_for_user(chat_id: int) -> list[Alert]:
    with Session(get_engine()) as session:
        return list(queries.get_active_alerts_for_user(session, chat_id))


async def get_alert_for_user(alert_id: int, chat_id: int) -> Alert | None:
    with Session(get_engine()) as session:
        return queries.get_alert_for_user(session, chat_id, alert_id)


async def delete_alert(alert_id: int, chat_id: int) -> dict:
    with Session(get_engine()) as session:
        deleted = queries.delete_alert_for_user(session, chat_id, alert_id)
        session.commit()
    return {"message": "Alerta removido"} if deleted else {"message": "Alerta não encontrado"}


# ── Matches / notificação (lê listing, escreve alert_matches) ──────────────
async def get_unnotified_listings(chat_id: int) -> list[ListingAlertMatch]:
    """Listings não notificados para os alertas ativos do usuário."""
    with Session(get_engine()) as session:
        return list(queries.get_unnotified_listings_for_user(session, chat_id))


async def mark_listings_notified(chat_id: int, pairs: list[tuple[int, int]]) -> dict:
    del chat_id  # alert_matches já carrega o alerta; chat é desnecessário aqui
    with Session(get_engine()) as session:
        queries.mark_listings_notified(session, pairs)
        session.commit()
    return {"status": "ok"}
