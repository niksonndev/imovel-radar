"""Registro do job diário no APScheduler, executado no mesmo processo do FastAPI."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config

from .jobs import job_daily

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> AsyncIOScheduler:
    """Cria e inicializa o scheduler com o job diário de scrape."""
    global _scheduler
    if _scheduler is not None:
        logger.warning("Scheduler já iniciado, ignorando.")
        return _scheduler

    tz = ZoneInfo(config.SCRAPE_TIMEZONE_NAME)
    _scheduler = AsyncIOScheduler()

    _scheduler.add_job(
        job_daily,
        trigger="cron",
        hour=config.SCRAPE_CRON_HOUR,
        minute=config.SCRAPE_CRON_MINUTE,
        timezone=tz,
        id="daily_scrape",
        name="daily_scrape",
        misfire_grace_time=300,
        coalesce=True,
    )

    _scheduler.start()

    now = datetime.now(tz)
    next_run = now.replace(
        hour=config.SCRAPE_CRON_HOUR,
        minute=config.SCRAPE_CRON_MINUTE,
        second=0,
        microsecond=0,
    )
    if next_run <= now:
        next_run += timedelta(days=1)

    logger.info(
        "Scheduler: próxima execução do job_daily às %s (%s)",
        next_run,
        config.SCRAPE_TIMEZONE_NAME,
    )
    return _scheduler


def stop_scheduler() -> None:
    """Para o scheduler (chamado no shutdown do FastAPI)."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler finalizado.")