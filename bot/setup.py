"""
Registra CommandHandlers, ConversationHandler e CallbackQueryHandlers no Application.
"""

from __future__ import annotations

from telegram import BotCommand
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from bot.callbacks import (
    alert_delete_cb,
    alert_toggle_cb,
    carousel_cb,
    menu_ajuda_cb,
    menu_home_cb,
    menu_meus_alertas_cb,
    menu_status_cb,
    menu_watchlist_cb,
    watch_remove_cb,
)
from bot.conversations import cancel_wiz, conversation_novo_alerta
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
            BotCommand("cancelar", "Cancela a conversa atual"),
        ]
    )


def setup(app: Application) -> None:
    """Registra todos os handlers de comandos, conversa e callbacks."""
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("meus_alertas", cmd_meus_alertas))
    app.add_handler(CommandHandler("pausar_alerta", cmd_pausar_alerta))
    app.add_handler(CommandHandler("deletar_alerta", cmd_deletar_alerta))
    app.add_handler(CommandHandler("observar", cmd_observar))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("remover", cmd_remover))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("ajuda", cmd_ajuda))
    app.add_handler(CommandHandler("cancelar", cancel_wiz))
    app.add_handler(conversation_novo_alerta())

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
    app.add_handler(
        CallbackQueryHandler(
            carousel_cb, pattern=r"^crs_\d+(?:_notif)?_(prev|next|pgp|pgn)$"
        )
    )
