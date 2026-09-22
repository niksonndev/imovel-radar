"""Camada de dados da Bot Lambda — acesso direto ao Postgres compartilhado (ADR 0005).

Lê/escreve no Postgres via SQLModel usando os table models de
``shared_models.tables``, que os handlers consomem diretamente (ver
``docs/bot-models-migration.md``). A bot é dona de
``users``/``alerts``/``alert_matches``/``watched_listings`` e lê ``listing``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal, NamedTuple

from shared_models.tables import (
    Alert,
    Listing,
    ListingAlertMatch,
    ListingKind,
    User,
    WatchedListingChange,
)
from sqlmodel import Session

from database import queries
from database.db import get_engine

logger = logging.getLogger(__name__)


class CreateAlertResult(NamedTuple):
    """Resultado de ``create_alert``: id, se inseriu agora, e status de freemium."""

    alert_id: int | None
    created: bool
    status: Literal["created", "reused", "cap_reached"]


CreateWatchStatus = Literal["created", "duplicate", "cap_reached", "listing_missing"]


class CreateWatchResult(NamedTuple):
    status: CreateWatchStatus
    watch_id: int | None


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


async def get_user(chat_id: int) -> User | None:
    with Session(get_engine()) as session:
        return queries.get_user(session, chat_id)


async def user_is_pro(chat_id: int) -> bool:
    with Session(get_engine()) as session:
        return queries.is_pro(queries.get_user(session, chat_id))


async def watch_cap_for_user(chat_id: int) -> int:
    with Session(get_engine()) as session:
        return queries.watch_cap_for(queries.get_user(session, chat_id))


async def activate_pro(
    *,
    chat_id: int,
    pro_until: datetime | None,
    telegram_payment_charge_id: str | None,
    subscription_active: bool = True,
) -> User:
    with Session(get_engine()) as session:
        user = queries.activate_pro(
            session,
            chat_id=chat_id,
            pro_until=pro_until,
            telegram_payment_charge_id=telegram_payment_charge_id,
            subscription_active=subscription_active,
        )
        session.commit()
        session.refresh(user)
        return user


async def claim_email_pro_trial(
    chat_id: int, email_raw: str
) -> tuple[queries.ClaimEmailProTrialStatus, User | None]:
    with Session(get_engine()) as session:
        status, user = queries.claim_email_pro_trial(
            session, chat_id=chat_id, email_raw=email_raw
        )
        if status == "activated" and user is not None:
            session.commit()
            session.refresh(user)
        return status, user


async def mark_pro_subscription_canceled(chat_id: int) -> User | None:
    with Session(get_engine()) as session:
        user = queries.mark_pro_subscription_canceled(session, chat_id)
        if user is not None:
            session.commit()
            session.refresh(user)
        return user


# ── Listings / bairros (read-only) ─────────────────────────────────────────
async def get_neighbourhoods(*, listing_kind: ListingKind | None = None) -> list[str]:
    with Session(get_engine()) as session:
        return queries.get_neighbourhoods(session, listing_kind=listing_kind)


async def get_listing(listing_id: int) -> Listing | None:
    with Session(get_engine()) as session:
        return queries.get_listing(session, listing_id)


# ── Alerts (dona: bot) ─────────────────────────────────────────────────────
async def create_alert(
    *,
    chat_id: int,
    alert_name: str,
    min_price: int | None = None,
    max_price: int | None = None,
    neighbourhoods: list[str],
    listing_kind: ListingKind = "aluguel",
    min_rooms: int | None = None,
    categories: list[str] | None = None,
) -> CreateAlertResult:
    """Cria o alerta (ou reusa um com os mesmos filtros) e indica se foi novo."""
    if min_price is None and max_price is None:
        raise ValueError("Informe min_price, max_price, ou ambos.")
    with Session(get_engine()) as session:
        existing = queries.find_equivalent_alert(
            session,
            chat_id=chat_id,
            min_price=min_price,
            max_price=max_price,
            neighbourhoods=neighbourhoods,
            listing_kind=listing_kind,
            min_rooms=min_rooms,
            categories=categories,
        )
        if existing is not None and existing.id is not None:
            return CreateAlertResult(
                alert_id=existing.id, created=False, status="reused"
            )

        user = queries.get_user(session, chat_id)
        cap = queries.alert_cap_for(user)
        if queries.count_active_alerts_for_user(session, chat_id) >= cap:
            return CreateAlertResult(alert_id=None, created=False, status="cap_reached")

        alert_id = queries.create_alert(
            session,
            chat_id=chat_id,
            alert_name=alert_name,
            min_price=min_price,
            max_price=max_price,
            neighbourhoods=neighbourhoods,
            listing_kind=listing_kind,
            min_rooms=min_rooms,
            categories=categories,
        )
        session.commit()
    return CreateAlertResult(alert_id=alert_id, created=True, status="created")


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


# ── Watchlist (dona: bot) ──────────────────────────────────────────────────
async def create_watch(*, chat_id: int, listing_id: int) -> CreateWatchResult:
    with Session(get_engine()) as session:
        status, watch_id = queries.create_watch(session, chat_id=chat_id, listing_id=listing_id)
        if status == "created":
            session.commit()
        return CreateWatchResult(status=status, watch_id=watch_id)  # type: ignore[arg-type]


async def get_watches_for_user(chat_id: int) -> list[WatchedListingChange]:
    with Session(get_engine()) as session:
        return list(queries.get_watches_for_user(session, chat_id))


async def get_watch_for_user(watch_id: int, chat_id: int) -> WatchedListingChange | None:
    with Session(get_engine()) as session:
        return queries.get_watch_for_user(session, chat_id, watch_id)


async def delete_watch(watch_id: int, chat_id: int) -> bool:
    with Session(get_engine()) as session:
        deleted = queries.delete_watch_for_user(session, chat_id, watch_id)
        session.commit()
        return deleted


async def get_changed_watches() -> list[WatchedListingChange]:
    with Session(get_engine()) as session:
        return list(queries.get_changed_watches(session))


async def update_watch_baselines(updates: list[tuple[int, int | None, bool]]) -> None:
    with Session(get_engine()) as session:
        queries.update_watch_baselines(session, updates)
        session.commit()
