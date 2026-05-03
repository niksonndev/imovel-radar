"""
Registra handlers no ``Application`` do python-telegram-bot.

Define os comandos exibidos no menu do Telegram (``set_my_commands``), o fluxo
``/novo_alerta`` (wizard em ``create_new_alert``), os comandos ``/start`` e
``/ajuda``, *Meus Alertas* (``bot.meus_alertas``) e o menu inline genérico (``menu_*``).
Os textos de UI ficam centralizados em ``bot.ui.menus``.
"""

from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from bot.carousel import register_handlers as register_carousel_handlers
from bot.create_new_alert import new_alert_conversation
from bot.meus_alertas import meus_alertas_actions_callback, meus_alertas_callback
from bot.ui import keyboards, menus

BOT_COMMANDS = [
    BotCommand("start", "Abre o menu principal"),
    BotCommand("novo_alerta", "Cria um novo alerta"),
    BotCommand("ajuda", "Mostra ajuda de uso"),
]


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        menus.start_welcome(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        menus.ajuda_comandos_plain(),
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def main_menu_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Roteia ações do menu principal mantendo navegação só por botões inline."""
    query = update.callback_query
    await query.answer()

    handlers: dict[str, tuple[str, bool]] = {
        "menu_watchlist": (menus.menu_watchlist(), True),
        "menu_ajuda": (menus.ajuda_comandos_plain(), False),
    }
    text, markdown = handlers.get(
        query.data or "",
        (menus.menu_principal_inline(), True),
    )
    await query.edit_message_text(
        text=text,
        parse_mode=ParseMode.MARKDOWN if markdown else None,
        reply_markup=keyboards.main_menu_keyboard(),
    )


def setup(app: Application) -> None:
    app.add_handler(new_alert_conversation())
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("ajuda", help_cmd))
    app.add_handler(
        CallbackQueryHandler(meus_alertas_callback, pattern=r"^menu_meus_alertas$")
    )
    app.add_handler(
        CallbackQueryHandler(meus_alertas_actions_callback, pattern=r"^mal_")
    )
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern=r"^menu_"))
    register_carousel_handlers(app)


async def apply_bot_commands(app: Application) -> None:
    """Publica os comandos do bot no menu do Telegram (``set_my_commands``)."""
    await app.bot.set_my_commands(BOT_COMMANDS)
