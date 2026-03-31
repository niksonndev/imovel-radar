"""
Handlers de comandos (/start, /ajuda, etc.).

Um comando → uma função async que delega a UI (teclados + textos).
"""

from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.novo_alerta_wizard import cancel_wiz, novo_alerta_entry
from bot.ui import keyboards, menus


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Exibe boas-vindas e mostra o menu principal."""
    context.user_data.clear()

    await update.message.reply_text(
        menus.start_welcome(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def cmd_meus_alertas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Informa indisponibilidade temporária da listagem de alertas."""
    await update.message.reply_text(menus.meus_alertas_unavailable())


async def cmd_pausar_alerta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Valida argumentos e responde sobre pausar/reativar alerta."""
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Uso: `/pausar_alerta [id]`", parse_mode=ParseMode.MARKDOWN
        )
        return
    try:
        int(args[0])
    except ValueError:
        await update.message.reply_text("ID inválido. Confira e tente novamente.")
        return
    await update.message.reply_text(menus.pausar_unavailable())


async def cmd_deletar_alerta(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Valida argumentos e responde sobre remoção de alerta."""
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Uso: `/deletar_alerta [id]`", parse_mode=ParseMode.MARKDOWN
        )
        return
    try:
        int(args[0])
    except ValueError:
        await update.message.reply_text("ID inválido. Confira e tente novamente.")
        return
    await update.message.reply_text(menus.deletar_unavailable())


async def cmd_observar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fluxo por URL em revisão."""
    await update.message.reply_text(
        menus.observar_unavailable(),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Informa indisponibilidade temporária da watchlist."""
    await update.message.reply_text(menus.watchlist_unavailable())


async def cmd_remover(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Valida argumentos e responde sobre remoção da watchlist."""
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Uso: `/remover [id]` (id da watchlist)",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    try:
        int(args[0])
    except ValueError:
        await update.message.reply_text("ID inválido. Confira e tente novamente.")
        return
    await update.message.reply_text(menus.remover_unavailable())


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra informações resumidas de status e próximas execuções."""
    watch_days = context.application.bot_data.get("watch_days", 1)
    next_a = context.application.bot_data.get("next_alert_run")
    next_w = context.application.bot_data.get("next_watch_run")
    na = next_a.strftime("%d/%m %H:%M") if next_a else "—"
    nw = next_w.strftime("%d/%m %H:%M") if next_w else "—"
    await update.message.reply_text(
        menus.status_command(watch_days=watch_days, next_alert=na, next_watch=nw),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra a lista de comandos disponíveis ao usuário."""
    await update.message.reply_text(
        menus.ajuda_comandos(),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_novo_alerta(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Inicia o wizard de criação de alerta (comando /novo_alerta)."""
    await novo_alerta_entry(update, context)


async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancela o wizard de novo alerta, se ativo."""
    await cancel_wiz(update, context)
