"""Consultas do banco usando SQLModel (sessões e ``select``).

O commit/rollback fica com o chamador (mesmo padrão do código antigo com
``sqlite3.Connection``). As funções de escrita apenas preparam objetos na
sessão; os endpoints/scheduler decidem quando commitar.

As queries acessam as colunas diretamente pelos modelos SQLModel, evitando
``__table__`` e mantendo type-check limpo.
"""

from __future__ import annotations

from shared_models.api_schemas import CreateAlertRequest, NotifiedPair
from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlmodel import Session, select

from collector.parser import RawAd

from .models import Alert, AlertMatch, Listing, ListingAlertMatch


# ── Listings ──────────────────────────────────────────────────────────────
def upsert_listing(session: Session, raw_ad: RawAd) -> None:
    """Persiste um anúncio bruto do scraper em ``listing`` usando UPSERT por ``listing_id``."""
    values = {
        "listing_id": raw_ad["listing_id"],
        "url": raw_ad["url"],
        "title": raw_ad["title"],
        "price_value": raw_ad["price_value"],
        "old_price": raw_ad["old_price"],
        "municipality": raw_ad["municipality"],
        "neighbourhood": raw_ad["neighbourhood"],
        "category": raw_ad["category"],
        "images": raw_ad["images"] or [],
        "properties": raw_ad["properties"],
        "active": True,
    }
    stmt = postgres_insert(Listing).values(**values)
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
    return list(
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


# ── Alerts ────────────────────────────────────────────────────────────────
def create_alert(session: Session, alert_data: CreateAlertRequest) -> int:
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
    stmt = select(Alert).where(Alert.chat_id == chat_id).order_by(Alert.id.desc())  # type: ignore[union-attr]  # pyright limitação: SQLModel column typing
    return list(session.exec(stmt).all())


def get_active_alerts_for_user(session: Session, chat_id: int) -> list[Alert]:
    stmt = (
        select(Alert)
        .where(Alert.chat_id == chat_id, Alert.active.is_(True))  # type: ignore[union-attr]  # pyright limitação: SQLModel column typing
        .order_by(Alert.id.desc())  # type: ignore[union-attr]  # pyright limitação: SQLModel column typing
    )
    return list(session.exec(stmt).all())


def delete_alert_for_user(session: Session, alert_id: int, chat_id: int) -> bool:
    stmt = select(Alert).where(Alert.id == alert_id, Alert.chat_id == chat_id)
    alert = session.exec(stmt).first()
    if alert is None:
        return False
    session.exec(delete(AlertMatch).where(AlertMatch.alert_id == alert_id))  # type: ignore[union-attr]  # pyright limitação: SQLModel column typing
    session.delete(alert)
    return True


# ── Alert matches ─────────────────────────────────────────────────────────
def get_unnotified_listings_for_alert(session: Session, alert: Alert) -> list[Listing]:
    conditions = [
        Listing.active.is_(True),  # type: ignore[union-attr]
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
            (AlertMatch.listing_id == Listing.listing_id) & (AlertMatch.alert_id == alert.id),  # type: ignore[union-attr]  # pyright limitação: SQLModel column typing
        )
        .where(*conditions)
        .order_by(Listing.updated_at.desc())  # type: ignore[union-attr]  # pyright limitação: SQLModel column typing
    )
    return list(session.exec(stmt).all())


def get_unnotified_listings_for_user(session: Session, chat_id: int) -> list[ListingAlertMatch]:
    alerts = get_active_alerts_for_user(session, chat_id)
    result: list[ListingAlertMatch] = []
    for alert in alerts:
        if alert.id is None:
            continue  # alerta ainda não persistido; não deveria ocorrer, não quebra silenciosamente
        listings = get_unnotified_listings_for_alert(session, alert)
        result.extend(ListingAlertMatch(listing=listing, alert_id=alert.id) for listing in listings)
    return result


def mark_listings_notified_bulk(session: Session, pairs: list[NotifiedPair]) -> None:
    session.add_all([AlertMatch(alert_id=p.alert_id, listing_id=p.listing_id) for p in pairs])
