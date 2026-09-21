"""Consultas do banco usando SQLModel (sessões e ``select``).

O commit/rollback fica com o chamador. A bot é dona de users/alerts/matches
(ADR 0005); o scraper só escreve ``listing``.
"""

from __future__ import annotations

from shared_models.tables import Listing
from sqlalchemy import func, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlmodel import Session, col, select

from collector.parser import RawAd


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


def deactivate_missing_listings(session: Session, seen_ids: set[int], municipality: str) -> int:
    """Marca como inativos os anúncios ativos do município que não vieram nesta coleta."""
    if not seen_ids:
        return 0
    stmt = (
        update(Listing)
        .where(
            col(Listing.active).is_(True),
            col(Listing.municipality) == municipality,
            col(Listing.listing_id).notin_(seen_ids),
        )
        .values(active=False, updated_at=func.now())
    )
    result = session.exec(stmt)
    return result.rowcount  # type: ignore[union-attr]


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
