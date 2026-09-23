"""
Registra handlers no ``Application`` do python-telegram-bot.
"""

import logging

from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
)

import config
from handlers.billing import register_billing_handlers
from handlers.carousel import register_handlers as register_carousel_handlers
from handlers.create_new_alert import new_alert_conversation
from handlers.email_pro_trial import email_pro_trial_conversation
from handlers.home import show_main_menu
from handlers.meus_alertas import meus_alertas_actions_callback, meus_alertas_callback
from handlers.ui import keyboards, menus
from handlers.watchlist import (
    carousel_watch_callback,
    watchlist_actions_callback,
    watchlist_menu_callback,
)
from models import CustomContext

logger = logging.getLogger(__name__)


def bot_commands() -> list[BotCommand]:
    cmds = [
        BotCommand("start", "Abre o menu principal"),
        BotCommand("novo_alerta", "Cria um novo alerta"),
    ]
    if config.BILLING_ENABLED:
        cmds.append(BotCommand("cancelar_pro", "Cancela a assinatura Radar Pro"))
    cmds.append(BotCommand("ajuda", "Mostra ajuda de uso"))
    return cmds


# Mantido para imports legados / testes.
BOT_COMMANDS = bot_commands()


async def start_cmd(update: Update, context: CustomContext) -> None:
    assert update.effective_message is not None
    await update.effective_message.reply_text(
        menus.start_welcome(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def help_cmd(update: Update, context: CustomContext) -> None:
    assert update.effective_message is not None
    await update.effective_message.reply_text(
        menus.ajuda_comandos_plain(),
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def main_menu_callback(update: Update, context: CustomContext) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    handlers: dict[str, tuple[str, bool]] = {
        "menu_ajuda": (menus.ajuda_comandos_plain(), False),
    }
    text, markdown = handlers.get(
        query.data or "",
        (menus.menu_principal_inline(), True),
    )
    if query.data not in handlers:
        logger.warning("Callback de menu não mapeado: %s", query.data)
    await query.edit_message_text(
        text=text,
        parse_mode=ParseMode.MARKDOWN if markdown else None,
        reply_markup=keyboards.main_menu_keyboard(),
    )


def setup(app: Application) -> None:
    # ConversationHandler primeiro: com o usuário no meio do wizard, /start e
    # /novo_alerta passam pelos fallbacks/entry (allow_reentry) e liberam o
    # estado preso. Fora do wizard, os CommandHandlers abaixo atendem.
    app.add_handler(new_alert_conversation())
    app.add_handler(email_pro_trial_conversation())
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("ajuda", help_cmd))

    # Handlers de callback específicos
    app.add_handler(CallbackQueryHandler(meus_alertas_callback, pattern=r"^menu_meus_alertas$"))
    app.add_handler(CallbackQueryHandler(meus_alertas_actions_callback, pattern=r"^mal_"))
    app.add_handler(CallbackQueryHandler(watchlist_menu_callback, pattern=r"^menu_watchlist$"))
    app.add_handler(
        CallbackQueryHandler(watchlist_actions_callback, pattern=r"^wl_(p_|rm_|m$|b$)")
    )
    app.add_handler(CallbackQueryHandler(carousel_watch_callback, pattern=r"^wch_\d+$"))
    app.add_handler(CallbackQueryHandler(show_main_menu, pattern=r"^menu_home$"))
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern=r"^menu_ajuda$"))
    register_billing_handlers(app)
    register_carousel_handlers(app)

    # Nota: a garantia de que o usuário existe no Postgres é feita de forma
    # global, antes de qualquer handler, via RadarApplication.process_update
    # (ver apps/bot/application.py).


async def apply_bot_commands(app: Application) -> None:
    await app.bot.set_my_commands(bot_commands())
