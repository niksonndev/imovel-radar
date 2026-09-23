"""Agrega anúncios ativos em um JSON de painel, por município e tipo.

Mediana (não média), com piso/teto de preço para cortar anúncio lixo.
Bairro só entra no ranking quando a amostra passa de ``MIN_SAMPLE``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from shared_models.tables import Listing, ListingKind, MarketSnapshot
from sqlalchemy import Float, Integer, and_, case, cast, func
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlmodel import Session, col, select

import config

MIN_SAMPLE = 15
NEW_WINDOW = timedelta(hours=36)
SIZE_MIN = 12
SIZE_MAX = 2_000
CONDO_MAX = 20_000

_DIGITS = r"^[0-9]+$"


def price_bounds(municipality: str, listing_kind: str) -> tuple[int, int]:
    """Piso e teto inclusivos do preço pedido, por cidade e tipo."""
    if listing_kind == "venda":
        if municipality == "Recife":
            return 50_000, 30_000_000
        return 40_000, 20_000_000
    if municipality == "Recife":
        return 400, 50_000
    return 300, 40_000


def _rint(value: object) -> int | None:
    if value is None:
        return None
    return int(round(float(value)))  # type: ignore[arg-type]


def _json_int(key: str):
    """Inteiro em ``properties`` só quando o texto é só dígitos; senão NULL."""
    raw = Listing.properties[key].as_string()
    return cast(case((raw.op("~")(_DIGITS), raw), else_=None), Integer)


def _size_expr():
    return _json_int("size")


def _ppm2_expr():
    size = _size_expr()
    return case(
        (
            and_(size >= SIZE_MIN, size <= SIZE_MAX),
            cast(Listing.price_value, Float) / size,
        ),
        else_=None,
    )


def _priced_filters(municipality: str, listing_kind: ListingKind) -> list[Any]:
    low, high = price_bounds(municipality, listing_kind)
    return [
        col(Listing.municipality) == municipality,
        col(Listing.listing_kind) == listing_kind,
        col(Listing.active).is_(True),
        col(Listing.price_value).is_not(None),
        col(Listing.price_value) >= low,
        col(Listing.price_value) <= high,
    ]


def _status_counts(
    session: Session, municipality: str, listing_kind: ListingKind
) -> tuple[int, int]:
    rows = session.execute(
        select(col(Listing.active), func.count())
        .where(
            col(Listing.municipality) == municipality,
            col(Listing.listing_kind) == listing_kind,
        )
        .group_by(col(Listing.active))
    ).all()
    active = inactive = 0
    for is_active, count in rows:
        if is_active:
            active = int(count)
        else:
            inactive = int(count)
    return active, inactive


def _price_summary(
    session: Session, municipality: str, listing_kind: ListingKind
) -> dict[str, Any]:
    ppm2 = _ppm2_expr()
    filters = _priced_filters(municipality, listing_kind)
    row = session.execute(
        select(
            func.count(),
            func.percentile_cont(0.25).within_group(col(Listing.price_value)),
            func.percentile_cont(0.5).within_group(col(Listing.price_value)),
            func.percentile_cont(0.75).within_group(col(Listing.price_value)),
            func.percentile_cont(0.5).within_group(ppm2),
            func.count(ppm2),
        ).where(*filters)
    ).one()
    return {
        "sample": int(row[0] or 0),
        "p25_price": _rint(row[1]),
        "median_price": _rint(row[2]),
        "p75_price": _rint(row[3]),
        "median_price_m2": _rint(row[4]),
        "price_m2_sample": int(row[5] or 0),
    }


def _rent_plus_condo(session: Session, municipality: str, listing_kind: ListingKind) -> int | None:
    if listing_kind != "aluguel":
        return None
    condo = _json_int("condominio")
    total = cast(Listing.price_value, Float) + condo
    row = session.execute(
        select(func.percentile_cont(0.5).within_group(total)).where(
            *_priced_filters(municipality, listing_kind),
            condo.is_not(None),
            condo <= CONDO_MAX,
        )
    ).one()
    return _rint(row[0])


def _new_count(
    session: Session,
    municipality: str,
    listing_kind: ListingKind,
    *,
    collected_at: datetime,
) -> int:
    cutoff = collected_at - NEW_WINDOW
    value = session.execute(
        select(func.count()).where(
            col(Listing.municipality) == municipality,
            col(Listing.listing_kind) == listing_kind,
            col(Listing.active).is_(True),
            col(Listing.first_seen_at).is_not(None),
            col(Listing.first_seen_at) >= cutoff,
        )
    ).scalar_one()
    return int(value or 0)


def _price_drop_count(session: Session, municipality: str, listing_kind: ListingKind) -> int:
    value = session.execute(
        select(func.count()).where(
            *_priced_filters(municipality, listing_kind),
            col(Listing.old_price).is_not(None),
            col(Listing.old_price) > col(Listing.price_value),
        )
    ).scalar_one()
    return int(value or 0)


def _by_category(
    session: Session, municipality: str, listing_kind: ListingKind
) -> list[dict[str, Any]]:
    ppm2 = _ppm2_expr()
    rows = session.execute(
        select(
            col(Listing.category),
            func.count(),
            func.percentile_cont(0.25).within_group(col(Listing.price_value)),
            func.percentile_cont(0.5).within_group(col(Listing.price_value)),
            func.percentile_cont(0.75).within_group(col(Listing.price_value)),
            func.percentile_cont(0.5).within_group(ppm2),
        )
        .where(*_priced_filters(municipality, listing_kind), col(Listing.category) != "")
        .group_by(col(Listing.category))
        .order_by(func.count().desc(), col(Listing.category))
    ).all()
    return [
        {
            "category": str(category),
            "sample": int(sample or 0),
            "p25_price": _rint(p25),
            "median_price": _rint(median),
            "p75_price": _rint(p75),
            "median_price_m2": _rint(median_m2),
        }
        for category, sample, p25, median, p75, median_m2 in rows
    ]


def _neighbourhoods(
    session: Session, municipality: str, listing_kind: ListingKind
) -> list[dict[str, Any]]:
    ppm2 = _ppm2_expr()
    rows = session.execute(
        select(
            col(Listing.neighbourhood),
            func.count(),
            func.percentile_cont(0.5).within_group(col(Listing.price_value)),
            func.percentile_cont(0.5).within_group(ppm2),
        )
        .where(*_priced_filters(municipality, listing_kind), col(Listing.neighbourhood) != "")
        .group_by(col(Listing.neighbourhood))
        .order_by(func.count().desc(), col(Listing.neighbourhood))
    ).all()
    stats: list[dict[str, Any]] = []
    for name, sample, median, median_m2 in rows:
        count = int(sample or 0)
        stats.append(
            {
                "name": str(name),
                "sample": count,
                "median_price": _rint(median),
                "median_price_m2": _rint(median_m2),
                "ranked": count >= MIN_SAMPLE,
            }
        )
    return stats


def _rooms(session: Session, municipality: str, listing_kind: ListingKind) -> list[dict[str, int]]:
    rooms = _json_int("rooms")
    rows = session.execute(
        select(rooms, func.count())
        .where(
            *_priced_filters(municipality, listing_kind),
            rooms.is_not(None),
            rooms >= 0,
            rooms <= 12,
        )
        .group_by(rooms)
        .order_by(rooms)
    ).all()
    return [
        {"rooms": int(room), "sample": int(sample or 0)}
        for room, sample in rows
        if room is not None
    ]


def _kind_stats(
    session: Session,
    municipality: str,
    listing_kind: ListingKind,
    *,
    collected_at: datetime,
) -> dict[str, Any]:
    active_count, inactive_count = _status_counts(session, municipality, listing_kind)
    summary = _price_summary(session, municipality, listing_kind)
    return {
        "active_count": active_count,
        "inactive_count": inactive_count,
        "new_count": _new_count(session, municipality, listing_kind, collected_at=collected_at),
        "price_drop_count": _price_drop_count(session, municipality, listing_kind),
        "median_rent_plus_condo": _rent_plus_condo(session, municipality, listing_kind),
        "by_category": _by_category(session, municipality, listing_kind),
        "neighbourhoods": _neighbourhoods(session, municipality, listing_kind),
        "rooms": _rooms(session, municipality, listing_kind),
        **summary,
    }


def build_market_snapshot(
    session: Session,
    *,
    collected_at: datetime | None = None,
) -> dict[str, Any]:
    """JSON do painel: uma entrada por cidade de ``config.MARKETS``."""
    moment = collected_at or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    cities: list[dict[str, Any]] = []
    for market in config.MARKETS:
        kinds: dict[str, Any] = {}
        for listing_kind in ("aluguel", "venda"):
            kinds[listing_kind] = _kind_stats(
                session,
                market.municipality,
                listing_kind,  # type: ignore[arg-type]
                collected_at=moment,
            )
        cities.append(
            {
                "key": market.key,
                "municipality": market.municipality,
                "kinds": kinds,
            }
        )
    return {
        "collected_at": moment.isoformat(),
        "min_sample": MIN_SAMPLE,
        "cities": cities,
    }


def save_market_snapshot(session: Session, payload: dict[str, Any]) -> None:
    """Uma linha por dia UTC. Nova coleta no mesmo dia substitui o payload."""
    collected_at = datetime.fromisoformat(str(payload["collected_at"]))
    if collected_at.tzinfo is None:
        collected_at = collected_at.replace(tzinfo=UTC)
    collected_on = collected_at.astimezone(UTC).date()
    stmt = postgres_insert(MarketSnapshot).values(
        collected_on=collected_on,
        collected_at=collected_at,
        payload=payload,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["collected_on"],
        set_={
            "collected_at": stmt.excluded.collected_at,
            "payload": stmt.excluded.payload,
        },
    )
    session.execute(stmt)


def latest_market_snapshot(session: Session) -> dict[str, Any] | None:
    row = session.exec(
        select(MarketSnapshot).order_by(col(MarketSnapshot.collected_on).desc())
    ).first()
    if row is None:
        return None
    payload = row.payload
    if isinstance(payload, str):
        import json

        loaded = json.loads(payload)
        return loaded if isinstance(loaded, dict) else None
    return payload
