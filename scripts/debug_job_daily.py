# scripts/debug_job_daily.py
"""
Dispara job_daily manualmente, fora do cron — para testar a migração
pro job_queue nativo do PTB sem esperar o horário configurado.

Uso: python -m scripts.debug_job_daily
"""

from __future__ import annotations

import asyncio
import logging

from telegram.ext import Application, ContextTypes

import config
from bot.setup import setup
from database import create_tables
from models import CustomContext, UserData
from scheduler.jobs import run_job_daily_now

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def main() -> None:
    create_tables()
    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .context_types(ContextTypes(context=CustomContext, user_data=UserData))
        .build()
    )
    setup(app)

    async with app:
        await app.start()
        try:
            logger.info("Disparando job_daily manualmente...")
            await run_job_daily_now(app)
            logger.info("job_daily concluído.")
        finally:
            await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
