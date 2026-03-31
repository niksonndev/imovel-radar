"""Registra CommandHandlers no Application e o menu de comandos do Telegram."""

from __future__ import annotations

from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.create_new_alert import cmd_novo_alerta
from bot.ui import keyboards, menus

BOT_COMMANDS: list[BotCommand] = [
    BotCommand("start", "Abre o menu principal"),
    BotCommand("novo_alerta", "Cria um novo alerta"),
    BotCommand("ajuda", "Mostra ajuda de uso"),
]


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Exibe boas-vindas e o menu principal."""
    msg = update.effective_message
    if msg is None:
        return
    text = menus.start_welcome() + menus.menu_principal_inline()
    await msg.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lista apenas os comandos expostos no menu do Telegram."""
    msg = update.effective_message
    if msg is None:
        return
    text = (
        "*Comandos*\n"
        "/start — boas-vindas e menu principal\n"
        "/novo_alerta — criar alerta de aluguel (preço, bairros, nome)\n"
        "/ajuda — esta mensagem"
    )
    await msg.reply_text(text, parse_mode=ParseMode.MARKDOWN)


def setup(app: Application) -> None:
    """Registra handlers e encadeia o envio do menu de comandos ao Telegram após o post_init existente."""
    previous = app.post_init

    async def _post_init_with_menu(application: Application) -> None:
        if previous is not None:
            await previous(application)
        await application.bot.set_my_commands(BOT_COMMANDS)

    app.post_init = _post_init_with_menu

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("novo_alerta", cmd_novo_alerta))
    app.add_handler(CommandHandler("ajuda", cmd_ajuda))
