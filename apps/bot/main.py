"""
Bot Telegram — cliente "dumb" da API do scraper.

Não acessa banco de dados nem faz scraping. Toda a lógica de negócio
(listings, alertas, matches) fica no serviço Scraper.

Responsabilidades:
- Traduzir a conversa do Telegram em chamadas HTTP para o scraper
- Polling periódico de matches novos (a cada 1 hora)
- Enviar notificações como carrosséis do Telegram
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from telegram.ext import Application, ContextTypes, PicklePersistence

import config
from handlers.setup import apply_bot_commands, setup
from jobs.polling_job import notify_new_matches
from models import CustomContext, UserData

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def post_init(app: Application) -> None:
    await apply_bot_commands(app)
    start_polling(app)
    logger.info("Bot iniciado.")


async def post_shutdown(app: Application) -> None:
    logger.info("Bot finalizado")


def start_polling(app: Application) -> None:
    """Agenda o job de polling de matches a cada 1 hora usando a JobQueue do PTB."""
    job_queue = app.job_queue
    assert job_queue is not None, "JobQueue indisponível — confirme o extra [job-queue] instalado"

    async def polling_wrapper(context: ContextTypes.DEFAULT_TYPE) -> None:
        await notify_new_matches(context.application)

    job_queue.run_repeating(
        polling_wrapper,
        interval=3600,  # 1 hora em segundos
        first=10,  # primeira execução 10 segundos após iniciar
        name="polling_matches",
    )
    logger.info("Polling de matches agendado: a cada 1 hora")


def main() -> None:
    persistence = PicklePersistence(filepath="carousel_state.pickle")

    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .context_types(ContextTypes(context=CustomContext, user_data=UserData))
        .persistence(persistence)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    setup(app)

    logger.info("Iniciando polling...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Parado pelo dev")