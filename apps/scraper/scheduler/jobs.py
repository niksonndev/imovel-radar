"""
Jobs agendados via APScheduler.

``job_daily`` é o job composto que roda 1x/dia: faz o full scrape e persiste
no banco. Não precisa enviar notificações — o bot faz polling dos matches.
"""

from __future__ import annotations

import logging

import scraper
from database import get_connection
from database.queries import upsert_listing

logger = logging.getLogger(__name__)


async def job_daily() -> dict[str, int]:
    """Coleta anúncios OLX e persiste no SQLite.

    Retorna um dict com ``success`` (bool) e ``count`` (int) para
    exposição via healthcheck, se desejado.
    """
    result: dict[str, int] = {"success": 0, "count": 0}
    try:
        logger.info("Coleta agendada: início")
        listings = await scraper.search_all_rent_maceio()
        conn = get_connection()
        try:
            for listing in listings:
                upsert_listing(conn, listing)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        logger.info("Coleta agendada: fim (%s anúncios)", len(listings))
        result["success"] = 1
        result["count"] = len(listings)
        return result
    except Exception:
        logger.exception("Coleta agendada falhou")
        return result