"""
O bot fica num loop infinito ouvindo o Telegram até você dar Ctrl+C.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from telegram.ext import Application

import config
from bot.setup import apply_bot_commands, setup
from database import create_tables
from scheduler.jobs import run_initial_scrape
from scheduler.setup import start_scheduler

if TYPE_CHECKING:
    from apscheduler.schedulers.background import BackgroundScheduler

# __file__ = caminho deste arquivo. .parent = pasta onde está o main.py.
# sys.path = lista de pastas onde o Python procura módulos ao dar "import".
# Sem isso, "import database" poderia falhar dependendo de onde você rodou o comando.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# logging = imprimir mensagens de debug/erro no terminal
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


# "async def" = função assíncrona (pode esperar rede/DB sem travar tudo).
# O python-telegram-bot chama isso depois que o app está pronto.
async def post_init(app: Application) -> None:
    global _scheduler

    await apply_bot_commands(app)

    # Checagem tem que vir ANTES de create_tables(): sqlite3.connect cria o
    # arquivo automaticamente, então depois dele DB_PATH.exists() é sempre True.
    db_was_missing = not config.DB_PATH.exists()
    create_tables()

    if db_was_missing:
        logger.info("imoveis.db não encontrado — rodando scrape inicial antes de iniciar o bot")
        # Scrape bloqueia (rede + SQLite); roda em thread para não travar o loop
        # do PTB. O polling só começa quando post_init retorna, então na primeira
        # subida o bot só responde depois que a base está populada.
        ok = await asyncio.to_thread(run_initial_scrape)
        if not ok:
            logger.warning(
                "Scrape inicial falhou; scheduler seguirá e tentará novamente no próximo cron"
            )

    # Captura o event loop do PTB para o scheduler despachar coroutines
    # (envio via Bot API) a partir da thread do BackgroundScheduler.
    loop = asyncio.get_running_loop()
    _scheduler = start_scheduler(app, loop)
    logger.info("Bot iniciado.")


async def post_shutdown(app: Application) -> None:
    # Ao fechar o programa: para o agendador
    global _scheduler
    if _scheduler is not None:
        await asyncio.to_thread(_scheduler.shutdown, True)
        _scheduler = None
    logger.info("Bot finalizado")


def main() -> None:
    # Application = coração da lib: token, handlers, polling
    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    setup(app)

    logger.info("🚀 Iniciando polling...")
    # Fica perguntando ao Telegram "tem mensagem nova?" o tempo todo
    app.run_polling(allowed_updates=["message", "callback_query"])


# Só roda main() se você executou "py main.py" diretamente
# (se outro arquivo importar main, não roda o bot sozinho)
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("🛑 Parado pelo dev")
