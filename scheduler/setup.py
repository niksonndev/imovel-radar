"""Registro do job diário na JobQueue nativa do python-telegram-bot."""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from telegram.ext import Application

import config
from scheduler.jobs import job_daily

logger = logging.getLogger(__name__)


def _next_run_at(hour: int, minute: int, tz: ZoneInfo) -> datetime:
    now = datetime.now(tz)
    next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    return next_run


def start_scheduler(app: Application) -> None:
    job_queue = app.job_queue
    assert job_queue is not None, "JobQueue indisponível — confirme o extra [job-queue] instalado"

    tz = ZoneInfo(config.SCRAPE_TIMEZONE_NAME)
    job_queue.run_daily(
        job_daily,
        time=time(hour=config.SCRAPE_CRON_HOUR, minute=config.SCRAPE_CRON_MINUTE, tzinfo=tz),
        name="daily",
        job_kwargs={"misfire_grace_time": 300, "coalesce": True},
    )

    logger.info(
        "Scheduler: próxima execução do job_daily às %s (%s)",
        _next_run_at(config.SCRAPE_CRON_HOUR, config.SCRAPE_CRON_MINUTE, tz),
        config.SCRAPE_TIMEZONE_NAME,
    )
