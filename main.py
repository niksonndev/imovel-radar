"""
PONTO DE ENTRADA DO PROGRAMA (equivalente ao index.js que você dá node).

Sempre rode na pasta do projeto:
  py main.py

O bot fica num loop infinito ouvindo o Telegram até você dar Ctrl+C.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# __file__ = caminho deste arquivo. .parent = pasta onde está o main.py.
# sys.path = lista de pastas onde o Python procura módulos ao dar "import".
# Sem isso, "import database" poderia falhar dependendo de onde você rodou o comando.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

import config
from bot.conversations import conversation_novo_alerta, conversation_acompanhar_anuncio
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
    menu_ajuda_cb,
    menu_meus_alertas_cb,
)
from database.crud import create_engine_and_session, init_db
from scheduler.jobs import register_jobs
from scraper.olx_scraper import OLXScraper

# logging = imprimir mensagens de debug/erro no terminal (tipo console.log)
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
)
logger = logging.getLogger(__name__)


# "async def" = função assíncrona (pode esperar rede/DB sem travar tudo).
# O python-telegram-bot chama isso depois que o app está pronto.
async def post_init(app: Application) -> None:
    # Conexão com SQLite + fábrica de "sessões" (cada operação no banco usa uma sessão)
    engine, session_factory = create_engine_and_session(config.DATABASE_URL)
    await init_db(engine)  # cria tabelas se não existirem

    # bot_data = "armário global" compartilhado por todo o bot (tipo um singleton)
    app.bot_data["engine"] = engine
    app.bot_data["session_factory"] = session_factory
    app.bot_data["scraper"] = OLXScraper()  # quem baixa páginas do OLX
    app.bot_data["alert_min"] = config.ALERT_CHECK_INTERVAL_MINUTES
    app.bot_data["watch_hours"] = config.WATCHLIST_CHECK_INTERVAL_HOURS

    # Agendador: dispara tarefas de tempo em tempo (tipo setInterval no Node)
    sched = AsyncIOScheduler()
    register_jobs(sched, app)
    sched.start()
    app.bot_data["scheduler"] = sched
    logger.info("Bot iniciado.")


async def post_shutdown(app: Application) -> None:
    # Ao fechar o programa: libera conexões HTTP e para o agendador
    scraper: OLXScraper = app.bot_data.get("scraper")
    if scraper:
        await scraper.close()
    sched = app.bot_data.get("scheduler")
    if sched:
        sched.shutdown(wait=False)


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
    # "👁 Acompanhar Anúncio" (conversa curta)
    app.add_handler(conversation_acompanhar_anuncio())
    logger.info("Polling…")
    # Fica perguntando ao Telegram "tem mensagem nova?" o tempo todo
    app.run_polling(allowed_updates=["message", "callback_query"])


# Só roda main() se você executou "py main.py" diretamente
# (se outro arquivo importar main, não roda o bot sozinho)
if __name__ == "__main__":
    main()
