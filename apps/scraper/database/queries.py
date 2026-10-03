"""Consultas do banco usando SQLModel (sessões e ``select``).

O commit/rollback fica com o chamador. A bot é dona de users/alerts/matches
(ADR 0005); o scraper só escreve ``listing``.
"""

from __future__ import annotations

from datetime import datetime

from shared_models.tables import CollectSlice, Listing, ListingKind
from sqlalchemy import func, or_, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlmodel import Session, col, select

from collector.parser import RawAd


def upsert_listing(session: Session, raw_ad: RawAd, *, source_market: str = "") -> None:
    """Persiste um anúncio bruto do scraper em ``listing`` usando UPSERT por ``listing_id``.

    ``source_market`` registra qual varredura viu o anúncio por último. É o que
    permite inativar pelo ESCOPO DA VARREDURA em vez do nome do município: a URL
    de Recife devolve a região metropolitana inteira, e filtrar por município
    deixava Jaboatão, Olinda e os outros crescendo para sempre sem nunca sair do
    ar (medido: 17.336 anúncios em 188 municípios, zero inativos).
    """
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
        "source_market": source_market,
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
            "source_market": stmt.excluded.source_market,
            "updated_at": func.now(),
        },
    )
    session.exec(stmt)


def marcar_fatia(
    session: Session,
    *,
    run_started_at: datetime,
    market: str,
    listing_kind: ListingKind,
    slice_index: int,
    status: str,
) -> None:
    """Registra como terminou uma fatia: ``ok``, ``clamped`` ou ``failed``."""
    values = {
        "run_started_at": run_started_at,
        "market": market,
        "listing_kind": listing_kind,
        "slice_index": slice_index,
        "status": status,
        "updated_at": func.now(),
    }
    stmt = postgres_insert(CollectSlice).values(**values)
    session.exec(
        stmt.on_conflict_do_update(
            index_elements=["run_started_at", "market", "listing_kind", "slice_index"],
            set_={"status": stmt.excluded.status, "updated_at": func.now()},
        )
    )


def fatias_pendentes(
    session: Session,
    *,
    run_started_at: datetime,
    market: str,
    listing_kind: ListingKind,
) -> int:
    """Quantas fatias marcadas neste run NÃO terminaram ``ok``.

    Zero significa que o walk viu o mercado/tipo inteiro e pode inativar o que
    não encontrou. Nenhuma fatia marcada (cadeia morta antes de terminar, erro
    no banco) também bloqueia: não viu nada, não inativa.
    """
    base = (
        select(func.count())
        .select_from(CollectSlice)
        .where(
            col(CollectSlice.run_started_at) == run_started_at,
            col(CollectSlice.market) == market,
            col(CollectSlice.listing_kind) == listing_kind,
        )
    )
    total = session.exec(base).one()
    if int(total) == 0:
        return 1
    problemas = session.exec(base.where(col(CollectSlice.status) != "ok")).one()
    return int(problemas)


def deactivate_missing_listings(
    session: Session,
    *,
    source_market: str,
    listing_kind: ListingKind,
    run_started_at: datetime,
) -> int:
    """Inativa anúncios ativos que esta varredura não tocou.

    O escopo é ``source_market`` (a varredura que viu o anúncio) e não
    ``municipality``: quem entra de carona na região metropolitana também
    precisa poder sair do ar.

    Usa ``updated_at < run_started_at`` (ou NULL) como watermark — seguro com
    coleta em chunks (não desativa páginas ainda não visitadas).
    """
    stmt = (
        update(Listing)
        .where(
            col(Listing.active).is_(True),
            col(Listing.source_market) == source_market,
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
