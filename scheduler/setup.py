from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

import config
from scheduler.jobs import job_full_scrape

logger = logging.getLogger(__name__)


def start_scheduler() -> BackgroundScheduler:
    """Inicia agendador em thread de fundo: coleta diária no horário configurado."""
    scheduler = BackgroundScheduler(timezone=config.SCRAPE_TIMEZONE)
    scheduler.add_job(
        job_full_scrape,
        trigger="cron",
        hour=config.SCRAPE_CRON_HOUR,
        minute=config.SCRAPE_CRON_MINUTE,
        id="full_scrape",
        replace_existing=True,
    )
    scheduler.start()
    job = scheduler.get_job("full_scrape")
    if job and job.next_run_time:
        logger.info(
            "Scheduler: próxima coleta às %s (%s)",
            job.next_run_time,
            config.SCRAPE_TIMEZONE_NAME,
        )
    return scheduler
