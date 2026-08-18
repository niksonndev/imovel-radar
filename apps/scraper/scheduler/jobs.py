"""Coleção diária do OLX.

``job_daily`` coleta e persiste; é invocada pelo EventBridge (Lambda) ou
manualmente (``uv run python -m scheduler.jobs``). Não notifica — quem lê
listings não notificados é o bot, direto do banco (ADR 0005).
"""

from __future__ import annotations

import asyncio
import logging

from sqlmodel import Session

import collector
from database import engine
from database.queries import upsert_listing

logger = logging.getLogger(__name__)


async def job_daily() -> dict[str, int]:
    """Collect OLX listings and persist to Postgres.

    Returns a dict with ``success`` (bool) and ``count`` (int).
    """
    result: dict[str, int] = {"success": 0, "count": 0}
    try:
        logger.info("Scheduled collection: start")
        listings = await collector.search_all_rent_maceio()
        with Session(engine) as session:
            for listing in listings:
                upsert_listing(session, listing)
            session.commit()

        logger.info("Scheduled collection: end (%s listings)", len(listings))
        result["success"] = 1
        result["count"] = len(listings)
        return result
    except Exception:
        logger.exception("Scheduled collection failed")
        return result


if __name__ == "__main__":
    asyncio.run(job_daily())
