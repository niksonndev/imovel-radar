"""
Bot Telegram — Imóvel Radar.

Dev local (/dev): roda com polling + PicklePersistence no fluxo ``main.py``.
Produção (serverless, ADR 0004): a Bot Lambda processa webhooks via
``lambda_handler.py`` com estado de conversa em DynamoDB (ADR 0006) e acesso
direto ao Postgres compartilhado (ADR 0005).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from telegram.ext import Application, ContextTypes, PicklePersistence

import config
from application import build_application
from handlers.setup import apply_bot_commands
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
    _ = app  # silencia hint de parâmetro não usado
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
    # Dev local: persistência por arquivo (PicklePersistence). Produção en serverless
    # usa DynamoDBPersistence via lambda_handler.py (ADR 0006).
    persistence = PicklePersistence(filepath=config.get_persistence_file())

    app = build_application(
        persistence=persistence,
        context_types=ContextTypes(context=CustomContext, user_data=UserData),
    )
    app.post_init = post_init
    app.post_shutdown = post_shutdown

    logger.info("Iniciando polling...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Parado pelo dev")