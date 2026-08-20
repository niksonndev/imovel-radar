"""Camada de dados da Bot Lambda — acesso direto ao Postgres compartilhado (ADR 0005).

Mantém o contrato (nomes/retornos) que os handlers já usavam da antiga API do
scraper, mas lê/escreve no Postgres via SQLModel. A bot é dona de
``users``/``alerts``/``alert_matches`` e lê ``listing``.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel
from shared_models.models import Alert, Listing, Properties
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


def to_shared_alert(a) -> Alert:  # noqa: ANN001 - SQLModel Alert
    assert a.id is not None
    return Alert(
        id=a.id,
        chat_id=a.chat_id,
        alert_name=a.alert_name,
        min_price=a.min_price,
        max_price=a.max_price,
        neighbourhoods=a.neighbourhoods,
        active=a.active,
        created_at=a.created_at,
    )


class _NewAlert(BaseModel):
    """Tipo retornado ao criar um alerta (compatível com o antigo CreateAlertResponse)."""

    id: int


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
async def create_alert(req: BaseModel) -> _NewAlert:
    with Session(engine) as session:
        alert_id = queries.create_alert(
            session,
            chat_id=req.chat_id,
            alert_name=req.alert_name,
            min_price=req.min_price,
            max_price=req.max_price,
            neighbourhoods=req.neighbourhoods,
        )
        session.commit()
    return _NewAlert(id=alert_id)


async def get_alerts_for_user(chat_id: int) -> list[Alert]:
    with Session(engine) as session:
        return [to_shared_alert(a) for a in queries.get_alerts_for_user(session, chat_id)]


async def get_active_alerts_for_user(chat_id: int) -> list[Alert]:
    with Session(engine) as session:
        return [to_shared_alert(a) for a in queries.get_active_alerts_for_user(session, chat_id)]


async def get_alert_for_user(alert_id: int, chat_id: int) -> Alert | None:
    with Session(engine) as session:
        a = queries.get_alert_for_user(session, chat_id, alert_id)
        return to_shared_alert(a) if a is not None else None


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


async def mark_listings_notified(chat_id: int, pairs: list) -> dict:
    del chat_id  # alert_matches já carrega o alerta; chat é desnecessário aqui
    with Session(engine) as session:
        queries.mark_listings_notified(session, [(p.alert_id, p.listing_id) for p in pairs])
        session.commit()
    return {"status": "ok"}
