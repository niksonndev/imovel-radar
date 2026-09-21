"""Consultas do banco usando SQLModel (sessões e ``select``).

O commit/rollback fica com o chamador. A bot é dona de users/alerts/matches
(ADR 0005); o scraper só escreve ``listing``.
"""

from __future__ import annotations

from datetime import datetime

from shared_models.tables import Listing, ListingKind
from sqlalchemy import func, or_, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlmodel import Session, col, select

from collector.parser import RawAd


def upsert_listing(session: Session, raw_ad: RawAd) -> None:
    """Persiste um anúncio bruto do scraper em ``listing`` usando UPSERT por ``listing_id``."""
    values = {
        "listing_id": raw_ad["listing_id"],
        "listing_kind": raw_ad["listing_kind"],
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
        "updated_at": func.now(),
    }
    stmt = postgres_insert(Listing).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["listing_id"],
        set_={
            "listing_kind": stmt.excluded.listing_kind,
            "price_value": stmt.excluded.price_value,
            "old_price": stmt.excluded.old_price,
            "url": stmt.excluded.url,
            "title": stmt.excluded.title,
            "municipality": stmt.excluded.municipality,
            "neighbourhood": stmt.excluded.neighbourhood,
            "category": stmt.excluded.category,
            "images": stmt.excluded.images,
            "properties": stmt.excluded.properties,
            "active": True,
            "updated_at": func.now(),
        },
    )
    session.exec(stmt)


def deactivate_missing_listings(
    session: Session,
    *,
    municipality: str,
    listing_kind: ListingKind,
    run_started_at: datetime,
) -> int:
    """Inativa anúncios ativos do município/kind não tocados nesta coleta completa.

    Usa ``updated_at < run_started_at`` (ou NULL) como watermark — seguro com
    coleta em chunks (não desativa páginas ainda não visitadas).
    """
    stmt = (
        update(Listing)
        .where(
            col(Listing.active).is_(True),
            col(Listing.municipality) == municipality,
            col(Listing.listing_kind) == listing_kind,
            or_(
                col(Listing.updated_at).is_(None),
                col(Listing.updated_at) < run_started_at,
            ),
        )
        .values(active=False, updated_at=func.now())
    )
    result = session.exec(stmt)
    return result.rowcount  # type: ignore[union-attr]


def get_neighbourhoods(
    session: Session,
    municipality: str,
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
