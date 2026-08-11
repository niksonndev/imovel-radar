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
    MessageHandler,
    filters,
)

from handlers.carousel import register_handlers as register_carousel_handlers
from handlers.create_new_alert import new_alert_conversation
from handlers.meus_alertas import meus_alertas_actions_callback, meus_alertas_callback
from handlers.ui import keyboards, menus
from handlers.user_guard import ensure_user_callback, ensure_user_message
from models import CustomContext

logger = logging.getLogger(__name__)

BOT_COMMANDS = [
    BotCommand("start", "Abre o menu principal"),
    BotCommand("novo_alerta", "Cria um novo alerta"),
    BotCommand("ajuda", "Mostra ajuda de uso"),
]


async def start_cmd(update: Update, context: CustomContext) -> None:
    assert update.effective_message
    await update.effective_message.reply_text(
        menus.start_welcome(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def help_cmd(update: Update, context: CustomContext) -> None:
    assert update.effective_message
    await update.effective_message.reply_text(
        menus.ajuda_comandos_plain(),
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def main_menu_callback(update: Update, context: CustomContext) -> None:
    query = update.callback_query
    assert query
    await query.answer()

    handlers: dict[str, tuple[str, bool]] = {
        "menu_watchlist": (menus.menu_watchlist(), True),
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
    # Verificação de usuário (genérica, executa primeiro)
    app.add_handler(CallbackQueryHandler(ensure_user_callback, pattern=r".*"))
    app.add_handler(MessageHandler(filters.ALL, ensure_user_message))

    # Fluxos de conversa devem ter prioridade sobre handlers genéricos
    app.add_handler(new_alert_conversation())
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("ajuda", help_cmd))
    app.add_handler(CallbackQueryHandler(meus_alertas_callback, pattern=r"^menu_meus_alertas$"))
    app.add_handler(CallbackQueryHandler(meus_alertas_actions_callback, pattern=r"^mal_"))
    app.add_handler(
        CallbackQueryHandler(main_menu_callback, pattern=r"^(menu_watchlist|menu_ajuda)$")
    )
    register_carousel_handlers(app)


async def apply_bot_commands(app: Application) -> None:
    await app.bot.set_my_commands(BOT_COMMANDS)
