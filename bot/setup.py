from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from bot.create_new_alert import new_alert_cmd, route_callback
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
        "*Comandos*\n"
        "/start — boas-vindas e menu principal\n"
        "/novo_alerta — criar alerta de aluguel\n"
        "/ajuda — esta mensagem",
        parse_mode=ParseMode.MARKDOWN,
    )


def setup(app: Application) -> None:
    async def _post_init(application: Application) -> None:
        await application.bot.set_my_commands(BOT_COMMANDS)

    app.post_init = _post_init

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("novo_alerta", new_alert_cmd))
    app.add_handler(CommandHandler("menu_ajuda", help_cmd))
    app.add_handler(CallbackQueryHandler(route_callback))
