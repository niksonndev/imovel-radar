"""Consultas da Bot Lambda no Postgres compartilhado (ADR 0005).

A bot lê ``listing`` (read-only), escreve ``users``/``alerts``/``alert_matches``/
``watched_listings``. O commit/rollback fica com o chamador.
"""

from __future__ import annotations

from shared_models.tables import (
    Alert,
    AlertMatch,
    Listing,
    ListingAlertMatch,
    ListingKind,
    User,
    WatchedListing,
    WatchedListingChange,
)
from sqlalchemy import delete, func, or_
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlmodel import Session, select

import config


# ── Users (dona: bot) ──────────────────────────────────────────────────────
def ensure_user(session: Session, chat_id: int) -> bool:
    """Garante a existência do usuário; cria se necessário (idempotente).

    Não commita — o chamador decide quando persistir.
    """
    stmt = postgres_insert(User).values(chat_id=chat_id).on_conflict_do_nothing()
    result = session.exec(stmt)
    return result.rowcount is not None  # True mesmo se nada inserido


def get_users_chat_ids(session: Session) -> list[int]:
    """Todos os chat_ids cadastrados (para o job de notificação)."""
    return list(session.exec(select(User.chat_id)).all())


# ── Neighbourhoods (lê listing) ────────────────────────────────────────────
def get_neighbourhoods(
    session: Session,
    municipality: str = "Maceió",
    *,
    listing_kind: ListingKind | None = None,
) -> list[str]:
    conditions = [
        Listing.municipality == municipality,
        Listing.neighbourhood != "",
    ]
    if listing_kind is not None:
        conditions.append(Listing.listing_kind == listing_kind)
    return list(
        session.exec(
            select(Listing.neighbourhood)
            .where(*conditions)
            .group_by(Listing.neighbourhood)
            .order_by(func.count().desc())
        ).all()
    )


# ── Listings (read-only) ───────────────────────────────────────────────────
def get_listing(session: Session, listing_id: int) -> Listing | None:
    return session.get(Listing, listing_id)


# ── Alerts (dona: bot) ─────────────────────────────────────────────────────
def create_alert(
    session: Session,
    *,
    chat_id: int,
    alert_name: str | None,
    min_price: int | None,
    max_price: int | None,
    neighbourhoods: list[str] | None,
    listing_kind: ListingKind = "aluguel",
) -> int:
    """Cria um alerta e retorna o id (o chamador decide quando commitar)."""
    alert = Alert(
        chat_id=chat_id,
        alert_name=alert_name,
        listing_kind=listing_kind,
        min_price=min_price,
        max_price=max_price,
        neighbourhoods=neighbourhoods,
    )
    session.add(alert)
    session.flush()  # preenche id sem commitar
    if alert.id is None:
        raise RuntimeError("Falha ao obter ID do alerta inserido")
    return alert.id


def find_equivalent_alert(
    session: Session,
    *,
    chat_id: int,
    min_price: int | None,
    max_price: int | None,
    neighbourhoods: list[str] | None,
    listing_kind: ListingKind = "aluguel",
) -> Alert | None:
    """Alerta já existente do usuário com os mesmos filtros (nome ignorado)."""
    wanted = sorted(neighbourhoods or [])
    for alert in get_alerts_for_user(session, chat_id):
        if (
            alert.listing_kind == listing_kind
            and alert.min_price == min_price
            and alert.max_price == max_price
            and sorted(alert.neighbourhoods or []) == wanted
        ):
            return alert
    return None


def get_alerts_for_user(session: Session, chat_id: int) -> list[Alert]:
    return list(
        session.exec(select(Alert).where(Alert.chat_id == chat_id).order_by(Alert.id.desc())).all()  # type: ignore[union-attr]
    )


def get_active_alerts_for_user(session: Session, chat_id: int) -> list[Alert]:
    return list(
        session.exec(
            select(Alert)
            .where(Alert.chat_id == chat_id, Alert.active.is_(True))  # type: ignore[union-attr]
            .order_by(Alert.id.desc())  # type: ignore[union-attr]
        ).all()
    )


def get_alert_for_user(session: Session, chat_id: int, alert_id: int) -> Alert | None:
    return session.exec(
        select(Alert).where(Alert.id == alert_id, Alert.chat_id == chat_id)
    ).one_or_none()


def delete_alert_for_user(session: Session, chat_id: int, alert_id: int) -> bool:
    alert = session.exec(
        select(Alert).where(Alert.id == alert_id, Alert.chat_id == chat_id)
    ).first()
    if alert is None:
        return False
    session.exec(delete(AlertMatch).where(AlertMatch.alert_id == alert_id))  # type: ignore[union-attr]
    session.delete(alert)
    return True


# ── Match / notificação (lê listing, escreve alert_matches) ────────────────
def get_unnotified_listings_for_alert(session: Session, alert: Alert) -> list[Listing]:
    conditions = [
        Listing.active.is_(True),  # type: ignore[union-attr]
        Listing.listing_kind == alert.listing_kind,
        AlertMatch.listing_id.is_(None),  # type: ignore[union-attr]
    ]
    if (min_price := alert.min_price) is not None:
        conditions.append(Listing.price_value >= min_price)  # type: ignore[union-attr]
    if (max_price := alert.max_price) is not None:
        conditions.append(Listing.price_value <= max_price)  # type: ignore[union-attr]
    if alert.neighbourhoods:
        conditions.append(Listing.neighbourhood.in_(alert.neighbourhoods))  # type: ignore[union-attr]

    stmt = (
        select(Listing)
        .outerjoin(
            AlertMatch,
            (AlertMatch.listing_id == Listing.listing_id) & (AlertMatch.alert_id == alert.id),  # type: ignore[union-attr]
        )
        .where(*conditions)
        .order_by(Listing.updated_at.desc())  # type: ignore[union-attr]
    )
    return list(session.exec(stmt).all())


def get_unnotified_listings_for_user(session: Session, chat_id: int) -> list[ListingAlertMatch]:
    """Listings ainda não notificados para os alertas ativos de um usuário."""
    result: list[ListingAlertMatch] = []
    for alert in get_active_alerts_for_user(session, chat_id):
        if alert.id is None:
            continue
        for listing in get_unnotified_listings_for_alert(session, alert):
            result.append(ListingAlertMatch(listing=listing, alert_id=alert.id))
    return result


def mark_listings_notified(session: Session, pairs: list[tuple[int, int]]) -> None:
    """Registra pares (alert_id, listing_id) como notificados (idempotente)."""
    if not pairs:
        return
    stmt = (
        postgres_insert(AlertMatch)
        .values(
            [
                {"alert_id": alert_id, "listing_id": listing_id}
                for alert_id, listing_id in pairs
            ]
        )
        .on_conflict_do_nothing(index_elements=["alert_id", "listing_id"])
    )
    session.exec(stmt)  # type: ignore[call-overload]


# ── Watchlist (dona: bot) ──────────────────────────────────────────────────
def count_watches_for_user(session: Session, chat_id: int) -> int:
    return int(
        session.exec(
            select(func.count())
            .select_from(WatchedListing)
            .where(WatchedListing.chat_id == chat_id)
        ).one()
    )


def get_watches_for_user(session: Session, chat_id: int) -> list[WatchedListingChange]:
    """Watches do usuário com o listing atual (mais recentes primeiro)."""
    rows = session.exec(
        select(WatchedListing, Listing)
        .join(Listing, Listing.listing_id == WatchedListing.listing_id)
        .where(WatchedListing.chat_id == chat_id)
        .order_by(WatchedListing.id.desc())  # type: ignore[union-attr]
    ).all()
    return [WatchedListingChange(watch=w, listing=listing) for w, listing in rows]


def get_watch_for_user(
    session: Session, chat_id: int, watch_id: int
) -> WatchedListingChange | None:
    row = session.exec(
        select(WatchedListing, Listing)
        .join(Listing, Listing.listing_id == WatchedListing.listing_id)
        .where(WatchedListing.id == watch_id, WatchedListing.chat_id == chat_id)
    ).one_or_none()
    if row is None:
        return None
    watch, listing = row
    return WatchedListingChange(watch=watch, listing=listing)


def get_watch_by_listing(
    session: Session, chat_id: int, listing_id: int
) -> WatchedListing | None:
    return session.exec(
        select(WatchedListing).where(
            WatchedListing.chat_id == chat_id,
            WatchedListing.listing_id == listing_id,
        )
    ).one_or_none()


def create_watch(session: Session, *, chat_id: int, listing_id: int) -> tuple[str, int | None]:
    """Cria acompanhamento. Retorna ``(status, watch_id)``.

    status: ``created`` | ``duplicate`` | ``cap_reached`` | ``listing_missing``
    """
    listing = get_listing(session, listing_id)
    if listing is None:
        return "listing_missing", None

    existing = get_watch_by_listing(session, chat_id, listing_id)
    if existing is not None:
        return "duplicate", existing.id

    if count_watches_for_user(session, chat_id) >= config.WATCHLIST_FREE_CAP:
        return "cap_reached", None

    watch = WatchedListing(
        chat_id=chat_id,
        listing_id=listing_id,
        last_known_price=listing.price_value,
        last_known_active=listing.active,
    )
    session.add(watch)
    session.flush()
    if watch.id is None:
        raise RuntimeError("Falha ao obter ID do acompanhamento inserido")
    return "created", watch.id


def delete_watch_for_user(session: Session, chat_id: int, watch_id: int) -> bool:
    watch = session.exec(
        select(WatchedListing).where(
            WatchedListing.id == watch_id,
            WatchedListing.chat_id == chat_id,
        )
    ).first()
    if watch is None:
        return False
    session.delete(watch)
    return True


def get_changed_watches(session: Session) -> list[WatchedListingChange]:
    """Watches cujo listing mudou de preço ou status ativo desde o baseline."""
    rows = session.exec(
        select(WatchedListing, Listing)
        .join(Listing, Listing.listing_id == WatchedListing.listing_id)
        .where(
            or_(
                Listing.price_value.is_distinct_from(WatchedListing.last_known_price),
                Listing.active.is_distinct_from(WatchedListing.last_known_active),
            )
        )
        .order_by(WatchedListing.chat_id, WatchedListing.id)
    ).all()
    return [WatchedListingChange(watch=w, listing=listing) for w, listing in rows]


def update_watch_baselines(
    session: Session,
    updates: list[tuple[int, int | None, bool]],
) -> None:
    """Atualiza baselines ``(watch_id, price, active)`` após notificar."""
    if not updates:
        return
    for watch_id, price, active in updates:
        watch = session.get(WatchedListing, watch_id)
        if watch is None:
            continue
        watch.last_known_price = price
        watch.last_known_active = active
        session.add(watch)
