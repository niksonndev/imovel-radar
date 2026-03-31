"""
Registra CommandHandlers, CallbackQueryHandler (roteador) e MessageHandler no Application.
"""

from __future__ import annotations

from telegram import BotCommand
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.handlers.callback_router import route_callback
from bot.handlers.start_handler import (
    cmd_ajuda,
    cmd_cancelar,
    cmd_deletar_alerta,
    cmd_meus_alertas,
    cmd_novo_alerta,
    cmd_observar,
    cmd_pausar_alerta,
    cmd_remover,
    cmd_start,
    cmd_status,
    cmd_watchlist,
)
from bot.handlers.text_input_handler import handle_wizard_text


async def setup_commands(app: Application) -> None:
    """Configura a lista de comandos exibida no menu do Telegram."""
    await app.bot.set_my_commands(
        [
            BotCommand("start", "Abre o menu principal"),
            BotCommand("meus_alertas", "Lista seus alertas"),
            BotCommand("observar", "Cria um novo alerta"),
            BotCommand("watchlist", "Mostra sua watchlist"),
            BotCommand("status", "Resumo do monitoramento"),
            BotCommand("ajuda", "Mostra ajuda de uso"),
            BotCommand("cancelar", "Cancela o wizard atual"),
        ]
    )


def setup(app: Application) -> None:
    """Registra todos os handlers de comandos, texto e callbacks."""
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("meus_alertas", cmd_meus_alertas))
    app.add_handler(CommandHandler("pausar_alerta", cmd_pausar_alerta))
    app.add_handler(CommandHandler("deletar_alerta", cmd_deletar_alerta))
    app.add_handler(CommandHandler("observar", cmd_observar))
    app.add_handler(CommandHandler("novo_alerta", cmd_novo_alerta))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("remover", cmd_remover))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("ajuda", cmd_ajuda))
    app.add_handler(CommandHandler("cancelar", cmd_cancelar))

    app.add_handler(CallbackQueryHandler(route_callback))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wizard_text)
    )
