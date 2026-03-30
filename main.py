"""
O bot fica num loop infinito ouvindo o Telegram até você dar Ctrl+C.
"""

from __future__ import annotations

import asyncio
import logging
import pickle
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from telegram.ext import Application, PicklePersistence

import config
from bot.setup import setup
from database import create_tables
from scheduler.setup import start_scheduler
from scraper import olx_scraper

if TYPE_CHECKING:
    from apscheduler.schedulers.background import BackgroundScheduler

# __file__ = caminho deste arquivo. .parent = pasta onde está o main.py.
# sys.path = lista de pastas onde o Python procura módulos ao dar "import".
# Sem isso, "import database" poderia falhar dependendo de onde você rodou o comando.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# logging = imprimir mensagens de debug/erro no terminal (tipo console.log)
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


class SafePicklePersistence(PicklePersistence):
    """PicklePersistence que descarta o arquivo se estiver corrompido ou inválido."""

    def _load_singlefile(self) -> None:
        try:
            super()._load_singlefile()
        except (TypeError, pickle.UnpicklingError, EOFError) as exc:
            logger.warning(
                "Arquivo de persistência PTB inválido (%s); removendo %s e iniciando vazio.",
                exc,
                self.filepath,
            )
            try:
                self.filepath.unlink(missing_ok=True)
            except OSError as unlink_err:
                logger.warning(
                    "Não foi possível remover persistência PTB: %s", unlink_err
                )
            self.conversations = {}
            self.user_data = {}
            self.chat_data = {}
            self.bot_data = self.context_types.bot_data()
            self.callback_data = None


# "async def" = função assíncrona (pode esperar rede/DB sem travar tudo).
# O python-telegram-bot chama isso depois que o app está pronto.
async def post_init(app: Application) -> None:
    create_tables()
    logger.info("Bot iniciado.")


async def post_shutdown(app: Application) -> None:
    # Ao fechar o programa: libera conexões HTTP e para o agendador
    global _scheduler
    await olx_scraper.close()
    if _scheduler is not None:
        await asyncio.to_thread(_scheduler.shutdown, True)
        _scheduler = None


def main() -> None:
    global _scheduler
    _scheduler = start_scheduler()
    persistence = SafePicklePersistence(filepath=config.PTB_PERSISTENCE_PATH)
    # Application = coração da lib: token, handlers, polling
    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .persistence(persistence)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    setup(app)
    logger.info("Polling…")
    # Fica perguntando ao Telegram "tem mensagem nova?" o tempo todo
    app.run_polling(allowed_updates=["message", "callback_query"])


# Só roda main() se você executou "py main.py" diretamente
# (se outro arquivo importar main, não roda o bot sozinho)
if __name__ == "__main__":
    main()
