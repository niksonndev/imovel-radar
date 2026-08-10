"""Jobs scheduled via APScheduler.

``job_daily`` is the composed job that runs 1x/day: performs the full scrape and
persists to the database. Does not need to send notifications — the bot polls for matches.
"""

from __future__ import annotations

import logging

from sqlmodel import Session

import collector
from database import engine
from database.queries import upsert_listing

logger = logging.getLogger(__name__)


async def job_daily() -> dict[str, int]:
    """Collect OLX listings and persist to SQLite.

    Returns a dict with ``success`` (bool) and ``count`` (int) for
    exposure via healthcheck, if desired.
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
