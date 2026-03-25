from __future__ import annotations

import asyncio
import logging
from collections import Counter

import config
from database import crud
from database.models import User
from database.crud import create_engine_and_session, init_db as init_models_db
from db.cache import deactivate_missing, upsert_listing
from db.database import init_db as init_cache_db
from db.parsers import parse_listing
from scheduler.jobs import _filter_listings_inhouse
from scraper import olx_scraper


logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
)
logger = logging.getLogger(__name__)


async def run_once() -> int:
    engine, session_factory = create_engine_and_session(config.DATABASE_URL)
    await init_models_db(engine)
    init_cache_db()

    cycle_seen_ids: set[int] = set()
    cache_stats = Counter({"created": 0, "updated": 0, "unchanged": 0})
    total_alerts = 0

    try:
        listings = await olx_scraper.search_all_rent_maceio()
        logger.info("Scrape global concluído com %s anúncio(s) brutos.", len(listings))

        for raw in listings:
            try:
                parsed = parse_listing(raw)
                result = upsert_listing(parsed)
                cache_stats[result] += 1
                cycle_seen_ids.add(parsed["list_id"])
            except Exception as exc:
                logger.warning("Falha no parse/upsert do anúncio: %s", exc)

        async with session_factory() as session:
            alerts = await crud.active_alerts(session)
            total_alerts = len(alerts)
        logger.info("Aplicando rastreamento em %s alerta(s) ativo(s).", total_alerts)

        for alert in alerts:
            if (alert.filters or {}).get("transaction") == "sale":
                filtered = []
            else:
                filtered = _filter_listings_inhouse(listings, alert.filters or {})
            async with session_factory() as session:
                user = await session.get(User, alert.user_id)
                if not user:
                    continue
                for ad in filtered:
                    oid = ad.get("listId")
                    if oid is None:
                        oid = ad.get("olx_id")
                    if oid:
                        await crud.mark_seen(session, alert.id, str(oid))
                await crud.update_alert_last_checked(session, alert.id)

        deactivated = deactivate_missing(list(cycle_seen_ids))
        logger.info(
            "Ciclo manual concluído | alertas=%s | stats=%s | desativados=%s",
            total_alerts,
            dict(cache_stats),
            deactivated,
        )
        return 0
    finally:
        await olx_scraper.close()
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_once()))
