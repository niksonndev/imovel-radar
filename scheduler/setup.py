"""Configuração do BackgroundScheduler e registro do job diário (cron).

Usamos ``BackgroundScheduler`` para o agendamento rodar numa thread separada:
o bot do python-telegram-bot mantém o próprio event loop na thread principal;
jobs em cron não bloqueiam o polling nem o processamento de updates.
"""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from telegram.ext import Application

import config
from scheduler.jobs import job_daily

logger = logging.getLogger(__name__)


def start_scheduler(
    app: Application,
    loop: asyncio.AbstractEventLoop,
) -> BackgroundScheduler:
    """Inicia agendador em thread de fundo: coleta diária + notificações.

    ``loop`` deve ser o event loop do PTB (capturado no ``post_init`` via
    ``asyncio.get_running_loop()``) — o job usa esse loop para despachar as
    chamadas assíncronas do Bot API.
    """
    # Fuso IANA vem do config (.env) para o horário do cron bater com o esperado localmente.
    scheduler = BackgroundScheduler(timezone=config.SCRAPE_TIMEZONE)
    scheduler.add_job(
        job_daily,
        trigger="cron",
        hour=config.SCRAPE_CRON_HOUR,
        minute=config.SCRAPE_CRON_MINUTE,
        id="daily",
        replace_existing=True,
        # Tolera pequenos atrasos (ex.: máquina hibernou um instante) sem
        # descartar a execução; mantém reprodutibilidade do horário diário.
        misfire_grace_time=300,
        # Várias execuções “atrasadas” viram uma só — evita rajada de scrapes/notificações.
        coalesce=True,
        # O job roda na thread do scheduler; app + loop do PTB permitem despachar coroutines na thread do bot.
        args=(app, loop),
    )
    scheduler.start()
    job = scheduler.get_job("daily")
    if job and job.next_run_time:
        logger.info(
            "Scheduler: próxima execução do job_daily às %s (%s)",
            job.next_run_time,
            config.SCRAPE_TIMEZONE_NAME,
        )
    return scheduler
