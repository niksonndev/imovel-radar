"""Camada de dados da Bot Lambda — acesso direto ao Postgres compartilhado (ADR 0005).

Mantém o contrato (nomes/retornos) que os handlers já usavam da antiga API do
scraper, mas lê/escreve no Postgres via SQLModel. A bot é dona de
``users``/``alerts``/``alert_matches`` e lê ``listing``.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel
from shared_models.models import Listing, Properties
from shared_models.tables import Alert
from sqlmodel import Session

from database import queries
from database.db import engine

logger = logging.getLogger(__name__)


# ── Conversões SQLModel -> shared_models (contrato dos handlers) ────────────
def to_shared_listing(listing) -> Listing:  # noqa: ANN001 - SQLModel Listing
    return Listing(
        listing_id=listing.listing_id,
        url=listing.url,
        title=listing.title,
        price_value=listing.price_value,
        old_price=listing.old_price,
        municipality=listing.municipality,
        neighbourhood=listing.neighbourhood,
        category=listing.category,
        images=listing.images,
        properties=Properties(**listing.properties) if listing.properties else Properties(),
        active=listing.active,
    )


class UnnotifiedListItem(Listing):
    """Listing não notificado + alerta que casou (compatível com UnnotifiedListing)."""

    alert_id: int


class UnnotifiedListingsResult(BaseModel):
    listings: list[UnnotifiedListItem]
    total: int


# ── Users (dona: bot) ──────────────────────────────────────────────────────
async def ensure_user(chat_id: int) -> bool:
    """Garante a existência do usuário; cria se necessário (idempotente)."""
    try:
        with Session(engine) as session:
            queries.ensure_user(session, chat_id)
        return True
    except Exception:
        logger.exception("Falha ao garantir usuário %s", chat_id)
        return False


async def create_user(chat_id: int) -> None:
    await ensure_user(chat_id)


async def get_user(chat_id: int) -> None:
    """Compat shim (não usado mais); a garantia é via ensure_user."""
    await ensure_user(chat_id)


# ── Listings / bairros (read-only) ─────────────────────────────────────────
async def get_neighbourhoods() -> list[str]:
    with Session(engine) as session:
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
    """Cria o alerta no Postgres e retorna o id gerado."""
    if min_price is None and max_price is None:
        raise ValueError("Informe min_price, max_price, ou ambos.")
    with Session(engine) as session:
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


# Nota (pedaço 1 da migração de modelos): retorna o table model direto —
# ver docs/bot-models-migration.md. O caminho Listing ainda converte.
async def get_alerts_for_user(chat_id: int) -> list[Alert]:
    with Session(engine) as session:
        return list(queries.get_alerts_for_user(session, chat_id))


async def get_active_alerts_for_user(chat_id: int) -> list[Alert]:
    with Session(engine) as session:
        return list(queries.get_active_alerts_for_user(session, chat_id))


async def get_alert_for_user(alert_id: int, chat_id: int) -> Alert | None:
    with Session(engine) as session:
        return queries.get_alert_for_user(session, chat_id, alert_id)


async def delete_alert(alert_id: int, chat_id: int) -> dict:
    with Session(engine) as session:
        deleted = queries.delete_alert_for_user(session, chat_id, alert_id)
        session.commit()
    return {"message": "Alerta removido"} if deleted else {"message": "Alerta não encontrado"}


# ── Matches / notificação (lê listing, escreve alert_matches) ──────────────
async def get_unnotified_listings(chat_id: int) -> UnnotifiedListingsResult:
    with Session(engine) as session:
        rows = queries.get_unnotified_listings_for_user(session, chat_id)
    items = [
        UnnotifiedListItem(**to_shared_listing(row.listing).model_dump(), alert_id=row.alert_id)
        for row in rows
    ]
    return UnnotifiedListingsResult(listings=items, total=len(items))


async def mark_listings_notified(chat_id: int, pairs: list[tuple[int, int]]) -> dict:
    del chat_id  # alert_matches já carrega o alerta; chat é desnecessário aqui
    with Session(engine) as session:
        queries.mark_listings_notified(session, pairs)
        session.commit()
    return {"status": "ok"}
