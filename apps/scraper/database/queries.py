"""Consultas do banco usando SQLModel (sessões e ``select``).

O commit/rollback fica com o chamador (mesmo padrão do código antigo com
``sqlite3.Connection``). As funções de escrita apenas preparam objetos na
sessão; os endpoints/scheduler decidem quando commitar.

As queries acessam as colunas diretamente pelos modelos SQLModel, evitando
``__table__`` e mantendo type-check limpo.
"""

from __future__ import annotations

from shared_models import CreateAlertData
from sqlalchemy import delete, func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import Session, select

from .models import Alert, AlertMatch, Listing, ListingAlertMatch


# ── Listings ──────────────────────────────────────────────────────────────
def upsert_listing(session: Session, listing: dict) -> None:
    """Faz ``INSERT ... ON CONFLICT DO UPDATE`` em ``listing`` por ``listing_id``."""
    values = {
        "listing_id": listing["listing_id"],
        "url": listing.get("url"),
        "title": listing.get("title"),
        "price_value": listing.get("price_value"),
        "old_price": listing.get("old_price"),
        "municipality": listing.get("municipality"),
        "neighbourhood": listing.get("neighbourhood"),
        "category": listing.get("category"),
        "images": listing.get("images") or [],
        "properties": listing.get("properties"),
        "active": True,
    }
    stmt = sqlite_insert(Listing).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["listing_id"],
        set_={
            "price_value": stmt.excluded.price_value,
            "old_price": stmt.excluded.old_price,
            "active": True,
            "updated_at": func.now(),
        },
    )
    session.exec(stmt)


def get_neighbourhoods(session: Session, municipality: str) -> list[str]:
    rows = list(
        session.exec(
            select(Listing.neighbourhood)
            .where(
                Listing.municipality == municipality,
                Listing.neighbourhood != "",
            )
            .group_by(Listing.neighbourhood)
            .order_by(func.count().desc())
        ).all()
    )
    return [row[0] for row in rows]


# ── Alerts ────────────────────────────────────────────────────────────────
def create_alert(session: Session, alert_data: CreateAlertData) -> int:
    alert = Alert(
        chat_id=alert_data.chat_id,
        alert_name=alert_data.alert_name,
        min_price=alert_data.min_price,
        max_price=alert_data.max_price,
        neighbourhoods=alert_data.neighbourhoods,
    )
    session.add(alert)
    session.flush()  # preenche id sem commitar (o chamador commita)
    if alert.id is None:
        raise RuntimeError("Falha ao obter ID do alerta inserido")
    return alert.id


def get_alert_for_user(session: Session, alert_id: int, chat_id: int) -> Alert | None:
    stmt = select(Alert).where(Alert.id == alert_id, Alert.chat_id == chat_id)
    return session.exec(stmt).one_or_none()


def get_alerts_for_user(session: Session, chat_id: int) -> list[Alert]:
    stmt = select(Alert).where(Alert.chat_id == chat_id).order_by(Alert.id.desc())
    return list(session.exec(stmt).all())


def get_active_alerts_for_user(session: Session, chat_id: int) -> list[Alert]:
    stmt = (
        select(Alert)
        .where(Alert.chat_id == chat_id, Alert.active.is_(True))
        .order_by(Alert.id.desc())
    )
    return list(session.exec(stmt).all())


def delete_alert_for_user(session: Session, alert_id: int, chat_id: int) -> bool:
    stmt = select(Alert).where(Alert.id == alert_id, Alert.chat_id == chat_id)
    alert = session.exec(stmt).first()
    if alert is None:
        return False
    session.exec(delete(AlertMatch).where(AlertMatch.alert_id == alert_id))
    session.delete(alert)
    return True


# ── Alert matches ─────────────────────────────────────────────────────────
def get_unnotified_listings_for_alert(session: Session, alert: Alert) -> list[Listing]:
    conditions = [
        Listing.active.is_(True),
        AlertMatch.listing_id.is_(None),
    ]
    if alert.min_price is not None:
        conditions.append(Listing.price_value >= alert.min_price)
    if alert.max_price is not None:
        conditions.append(Listing.price_value <= alert.max_price)
    if alert.neighbourhoods:
        conditions.append(Listing.neighbourhood.in_(alert.neighbourhoods))

    stmt = (
        select(Listing)
        .outerjoin(
            AlertMatch,
            (AlertMatch.listing_id == Listing.listing_id) & (AlertMatch.alert_id == alert.id),
        )
        .where(*conditions)
        .order_by(Listing.updated_at.desc())
    )
    return list(session.exec(stmt).all())


def get_unnotified_listings_for_user(session: Session, chat_id: int) -> list[ListingAlertMatch]:
    alerts = get_active_alerts_for_user(session, chat_id)
    result: list[ListingAlertMatch] = []
    for alert in alerts:
        listings = get_unnotified_listings_for_alert(session, alert)
        result.extend(ListingAlertMatch(listing=listing, alert_id=alert.id) for listing in listings)
    return result


def mark_listings_notified(session: Session, alert_id: int, listing_ids: list[int]) -> None:
    session.add_all(
        [
            AlertMatch(
                alert_id=alert_id,
                listing_id=listing_id,
            )
            for listing_id in listing_ids
        ]
    )
