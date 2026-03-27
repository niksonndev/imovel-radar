"""
O bot fica num loop infinito ouvindo o Telegram até você dar Ctrl+C.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from telegram.ext import Application, CommandHandler, CallbackQueryHandler

import config
from bot.carousel import carousel_cb
from bot.conversations import conversation_novo_alerta
from bot.handlers import (
    alert_delete_cb,
    alert_toggle_cb,
    cmd_ajuda,
    cmd_deletar_alerta,
    cmd_meus_alertas,
    cmd_observar,
    cmd_pausar_alerta,
    cmd_remover,
    cmd_start,
    cmd_status,
    cmd_watchlist,
    menu_ajuda_cb,
    menu_home_cb,
    menu_meus_alertas_cb,
    menu_status_cb,
    menu_watchlist_cb,
    watch_remove_cb,
)
from database import create_tables
from scraper import olx_scraper

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


# "async def" = função assíncrona (pode esperar rede/DB sem travar tudo).
# O python-telegram-bot chama isso depois que o app está pronto.
async def post_init(app: Application) -> None:
    create_tables()
    logger.info("Bot iniciado.")


async def post_shutdown(app: Application) -> None:
    # Ao fechar o programa: libera conexões HTTP e para o agendador
    await olx_scraper.close()


def main() -> None:
    # Application = coração da lib: token, handlers, polling
    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    # Cada CommandHandler liga um texto (/start) a uma função async (cmd_start)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("meus_alertas", cmd_meus_alertas))
    app.add_handler(CommandHandler("pausar_alerta", cmd_pausar_alerta))
    app.add_handler(CommandHandler("deletar_alerta", cmd_deletar_alerta))
    app.add_handler(CommandHandler("observar", cmd_observar))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("remover", cmd_remover))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("ajuda", cmd_ajuda))
    # ConversationHandler = vários passos numa conversa (/novo_alerta)
    app.add_handler(conversation_novo_alerta())
    # Menu principal (botões inline)
    app.add_handler(
        CallbackQueryHandler(menu_meus_alertas_cb, pattern=r"^menu_meus_alertas$")
    )
    app.add_handler(CallbackQueryHandler(menu_ajuda_cb, pattern=r"^menu_ajuda$"))
    app.add_handler(CallbackQueryHandler(menu_home_cb, pattern=r"^menu_home$"))
    app.add_handler(
        CallbackQueryHandler(menu_watchlist_cb, pattern=r"^menu_watchlist$")
    )
    app.add_handler(CallbackQueryHandler(menu_status_cb, pattern=r"^menu_status$"))
    app.add_handler(
        CallbackQueryHandler(alert_toggle_cb, pattern=r"^alert_toggle_\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(alert_delete_cb, pattern=r"^alert_delete_\d+$")
    )
    app.add_handler(
        CallbackQueryHandler(watch_remove_cb, pattern=r"^watch_remove_\d+$")
    )
    # Carrossel de anúncios (navegação inline após seed imediato)
    app.add_handler(
        CallbackQueryHandler(
            carousel_cb, pattern=r"^crs_\d+(?:_notif)?_(prev|next|pgp|pgn)$"
        )
    )
    logger.info("Polling…")
    # Fica perguntando ao Telegram "tem mensagem nova?" o tempo todo
    app.run_polling(allowed_updates=["message", "callback_query"])


# Só roda main() se você executou "py main.py" diretamente
# (se outro arquivo importar main, não roda o bot sozinho)
if __name__ == "__main__":
    main()
