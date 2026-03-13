"""
Entrada do bot Telegram (alertas OLX Maceió).

Sempre execute na RAIZ do repositório (pasta imovel-radar):
  py main.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Garante que imports como `database`, `bot`, `scraper` funcionem
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application, CommandHandler

import config
from bot.conversations import conversation_novo_alerta
from bot.handlers import (
    cmd_ajuda,
    cmd_deletar_alerta,
    cmd_meus_alertas,
    cmd_observar,
    cmd_pausar_alerta,
    cmd_remover,
    cmd_start,
    cmd_status,
    cmd_watchlist,
)
from database.crud import create_engine_and_session, init_db
from scheduler.jobs import register_jobs
from scraper.olx_scraper import OLXScraper

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
)
logger = logging.getLogger(__name__)


async def post_init(app: Application) -> None:
    engine, session_factory = create_engine_and_session(config.DATABASE_URL)
    await init_db(engine)
    app.bot_data["engine"] = engine
    app.bot_data["session_factory"] = session_factory
    app.bot_data["scraper"] = OLXScraper()
    app.bot_data["alert_min"] = config.ALERT_CHECK_INTERVAL_MINUTES
    app.bot_data["watch_hours"] = config.WATCHLIST_CHECK_INTERVAL_HOURS
    sched = AsyncIOScheduler()
    register_jobs(sched, app)
    sched.start()
    app.bot_data["scheduler"] = sched
    logger.info("Bot iniciado.")


async def post_shutdown(app: Application) -> None:
    scraper: OLXScraper = app.bot_data.get("scraper")
    if scraper:
        await scraper.close()
    sched = app.bot_data.get("scheduler")
    if sched:
        sched.shutdown(wait=False)


def main() -> None:
    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("meus_alertas", cmd_meus_alertas))
    app.add_handler(CommandHandler("pausar_alerta", cmd_pausar_alerta))
    app.add_handler(CommandHandler("deletar_alerta", cmd_deletar_alerta))
    app.add_handler(CommandHandler("observar", cmd_observar))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("remover", cmd_remover))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("ajuda", cmd_ajuda))
    app.add_handler(conversation_novo_alerta())
    logger.info("Polling…")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
