from __future__ import annotations

import logging

import scraper
from database import get_connection
from database.queries import upsert_listing

logger = logging.getLogger(__name__)


def job_full_scrape() -> None:
    """Coleta anúncios OLX e persiste no SQLite; erros são logados, não propagados."""
    try:
        logger.info("Coleta agendada: início")
        listings = scraper.coletar()
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
    except Exception:
        logger.exception("Coleta agendada falhou")
        return
