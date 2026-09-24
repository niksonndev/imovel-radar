"""Coleção diária do OLX (aluguel + venda), em chunks por invocação Lambda.

``job_collect_chunk`` coleta uma janela de páginas, persiste, e retorna
metadados para o handler decidir self-invoke / deactivate. Notificações
continuam responsabilidade do bot (ADR 0005).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, Callable

from shared_models.tables import ListingKind
from sqlmodel import Session

import config
from collector import base_url_for_kind, search_listings
from database import engine
from database.queries import deactivate_missing_listings, upsert_listing

logger = logging.getLogger(__name__)

RemainingTimeFn = Callable[[], int | None]
PriceSlice = tuple[int | None, int | None]


def slices_for_kind(
    listing_kind: ListingKind,
    market: str | None = None,
) -> list[PriceSlice]:
    """Fatias de preço da coleta daquele mercado e tipo."""
    chosen = config.market_by_key(market)
    if listing_kind == "venda":
        return list(chosen.sale_slices)
    return list(chosen.rent_slices)


def should_deactivate_after_slice(
    listing_kind: ListingKind,
    slice_index: int,
    *,
    completed: bool,
    market: str | None = None,
    skip_deactivate: bool = False,
) -> bool:
    """Desativa só quando a última fatia do kind terminou de verdade."""
    if skip_deactivate or not completed:
        return False
    slices = slices_for_kind(listing_kind, market)
    return slice_index == len(slices) - 1


def parse_run_started_at(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(UTC)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def normalize_kind(raw: Any) -> ListingKind:
    if raw == "venda":
        return "venda"
    return "aluguel"


async def job_collect_chunk(
    *,
    listing_kind: ListingKind = "aluguel",
    market: str | None = None,
    start_page: int = 1,
    slice_index: int = 0,
    attempt: int = 0,
    skip_deactivate: bool = False,
    run_started_at: datetime | None = None,
    get_remaining_ms: RemainingTimeFn | None = None,
    max_pages: int | None = None,
) -> dict[str, Any]:
    """Coleta uma janela de páginas de uma fatia e persiste.

    Returns:
      success, count, market, listing_kind, slice_index, completed, clamped,
      next_page, attempt, run_started_at (iso), deactivated (int, só na última
      fatia concluída), skip_deactivate.
    """
    chosen = config.market_by_key(market)
    started = run_started_at or datetime.now(UTC)
    slices = slices_for_kind(listing_kind, chosen.key)
    result: dict[str, Any] = {
        "success": 0,
        "count": 0,
        "market": chosen.key,
        "listing_kind": listing_kind,
        "slice_index": slice_index,
        "completed": False,
        "clamped": False,
        "next_page": None,
        "attempt": attempt,
        "skip_deactivate": skip_deactivate,
        "run_started_at": started.isoformat(),
        "deactivated": 0,
    }
    if slice_index < 0 or slice_index >= len(slices):
        logger.error(
            "slice_index inválido: %s (kind=%s, fatias=%s)",
            slice_index,
            listing_kind,
            len(slices),
        )
        return result

    price_min, price_max = slices[slice_index]
    try:
        logger.info(
            "Collect chunk: start market=%s kind=%s slice=%s/%s page=%s attempt=%s "
            "ps=%s pe=%s run_started_at=%s",
            chosen.key,
            listing_kind,
            slice_index,
            len(slices) - 1,
            start_page,
            attempt,
            price_min,
            price_max,
            started.isoformat(),
        )
        chunk = await search_listings(
            base_url_for_kind(listing_kind, market_key=chosen.key),
            listing_kind=listing_kind,
            start_page=start_page,
            max_pages=max_pages,
            price_min=price_min,
            price_max=price_max,
            attempt=attempt,
            get_remaining_ms=get_remaining_ms,
        )
        deactivate = should_deactivate_after_slice(
            listing_kind,
            slice_index,
            completed=chunk.completed,
            market=chosen.key,
            skip_deactivate=skip_deactivate or chunk.clamped,
        )
        with Session(engine) as session:
            for listing in chunk.listings:
                upsert_listing(session, listing)
            deactivated = 0
            if deactivate:
                deactivated = deactivate_missing_listings(
                    session,
                    municipality=chosen.municipality,
                    listing_kind=listing_kind,
                    run_started_at=started,
                )
                logger.info(
                    "Deactivated %s missing listings (kind=%s slice=%s)",
                    deactivated,
                    listing_kind,
                    slice_index,
                )
            elif chunk.completed:
                logger.info(
                    "Fatia %s concluída (kind=%s) — sem deactivate; próxima fatia segue",
                    slice_index,
                    listing_kind,
                )
            session.commit()

        result["success"] = 1
        result["count"] = len(chunk.listings)
        result["completed"] = chunk.completed
        result["clamped"] = chunk.clamped
        result["next_page"] = chunk.next_page
        result["attempt"] = chunk.next_attempt
        result["skip_deactivate"] = skip_deactivate or chunk.clamped
        result["deactivated"] = deactivated
        logger.info(
            "Collect chunk: end market=%s kind=%s slice=%s count=%s completed=%s "
            "clamped=%s next_page=%s attempt=%s",
            chosen.key,
            listing_kind,
            slice_index,
            result["count"],
            chunk.completed,
            chunk.clamped,
            chunk.next_page,
            chunk.next_attempt,
        )
        return result
    except Exception:
        logger.exception("Collect chunk failed (kind=%s slice=%s)", listing_kind, slice_index)
        return result


async def job_daily() -> dict[str, int]:
    """Compat local/manual: coleta aluguel de Maceió até o fim (uma janela grande)."""
    maceio = config.market_by_key("maceio")
    started = datetime.now(UTC)
    total = 0
    page = 1
    while True:
        chunk = await search_listings(
            base_url_for_kind("aluguel", market_key=maceio.key),
            listing_kind="aluguel",
            start_page=page,
            max_pages=config.SCRAPER_MAX_PAGES,
        )
        with Session(engine) as session:
            for listing in chunk.listings:
                upsert_listing(session, listing)
            if chunk.completed and not chunk.clamped:
                deactivate_missing_listings(
                    session,
                    municipality=maceio.municipality,
                    listing_kind="aluguel",
                    run_started_at=started,
                )
            session.commit()
        total += len(chunk.listings)
        if chunk.completed or not chunk.next_page:
            break
        page = chunk.next_page
    return {"success": 1, "count": total}


if __name__ == "__main__":
    asyncio.run(job_daily())
