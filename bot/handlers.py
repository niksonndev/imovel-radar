"""
HANDLERS = uma função por COMANDO do Telegram (/start, /observar, ...).

Quando alguém manda /start, a lib chama cmd_start(update, context).
- update = dados da mensagem (quem mandou, texto, etc.)
- context = acesso ao bot_data, args do comando, etc.

async def = a função pode usar await (responder no Telegram, banco, OLX).
"""

from __future__ import annotations

from telegram.constants import ParseMode
from telegram import Update
from telegram.ext import ContextTypes

from bot import keyboards


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Exibe boas-vindas e mostra o menu principal."""
    # /start também funciona como "reset geral" de estado da conversa.
    context.user_data.clear()

    # Escrita no banco removida:
    # async with _session(context) as session:
    #     await crud.get_or_create_user(
    #         session, update.effective_user.id, update.effective_user.username
    #     )
    await update.message.reply_text(
        "👋 *Olá!* Sou o bot de alertas OLX — *Maceió/AL*.\n\n",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def cmd_meus_alertas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Informa indisponibilidade temporária da listagem de alertas."""
    # Escrita no banco removida (get_or_create_user):
    # async with _session(context) as session:
    #     user = await crud.get_or_create_user(
    #         session, update.effective_user.id, update.effective_user.username
    #     )
    #     alerts = await crud.list_alerts(session, user.id)
    await update.message.reply_text(
        "📋 Meus alertas está temporariamente indisponível. Tente novamente em instantes."
    )


async def cmd_pausar_alerta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Valida argumentos e responde sobre pausar/reativar alerta."""
    # context.args = palavras depois do comando: /pausar_alerta 3 → ["3"]
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Uso: `/pausar_alerta [id]`", parse_mode=ParseMode.MARKDOWN
        )
        return
    try:
        aid = int(args[0])
    except ValueError:
        await update.message.reply_text("ID inválido. Confira e tente novamente.")
        return
    # Escrita no banco removida:
    # async with _session(context) as session:
    #     user = await crud.get_or_create_user(
    #         session, update.effective_user.id, update.effective_user.username
    #     )
    #     active = await crud.toggle_alert_active(session, aid, user.id)
    await update.message.reply_text(
        "⏸️ Pausar/reativar alerta está temporariamente indisponível."
    )


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
        aid = int(args[0])
    except ValueError:
        await update.message.reply_text("ID inválido. Confira e tente novamente.")
        return
    # Escrita no banco removida:
    # async with _session(context) as session:
    #     user = await crud.get_or_create_user(
    #         session, update.effective_user.id, update.effective_user.username
    #     )
    #     ok = await crud.delete_alert(session, aid, user.id)
    await update.message.reply_text(
        "🗑️ Deletar alerta está temporariamente indisponível."
    )


async def cmd_observar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fluxo por URL em revisão; watchlist via jobs continua usando fetch_listing no scheduler."""
    await update.message.reply_text(
        "`/observar` por URL está temporariamente indisponível.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Informa indisponibilidade temporária da watchlist."""
    # Escrita no banco removida (get_or_create_user):
    # async with _session(context) as session:
    #     user = await crud.get_or_create_user(
    #         session, update.effective_user.id, update.effective_user.username
    #     )
    #     items = await crud.list_watched(session, user.id)
    await update.message.reply_text(
        "👀 Watchlist está temporariamente indisponível. Tente novamente em instantes."
    )


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
        wid = int(args[0])
    except ValueError:
        await update.message.reply_text("ID inválido. Confira e tente novamente.")
        return
    # Escrita no banco removida:
    # async with _session(context) as session:
    #     user = await crud.get_or_create_user(
    #         session, update.effective_user.id, update.effective_user.username
    #     )
    #     ok = await crud.remove_watched(session, wid, user.id)
    await update.message.reply_text(
        "🧹 Remover da watchlist está temporariamente indisponível."
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra informações resumidas de status e próximas execuções."""
    # Horários que o scheduler atualizou em bot_data (próxima janela aproximada)
    scrape_days = context.application.bot_data.get("scrape_days", 1)
    watch_days = context.application.bot_data.get("watch_days", 1)
    next_a = context.application.bot_data.get("next_alert_run")
    next_w = context.application.bot_data.get("next_watch_run")
    na = next_a.strftime("%d/%m %H:%M") if next_a else "—"
    nw = next_w.strftime("%d/%m %H:%M") if next_w else "—"
    await update.message.reply_text(
        f"*Status*\n"
        f"• Scrape/alertas: diariamente às *03:00* (Maceió) (próx.: _{na}_)\n"
        f"• Watchlist: a cada *{watch_days}* dia(s) (próx.: _{nw}_)\n"
        f"• Região: Maceió/AL",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra a lista de comandos disponíveis ao usuário."""
    await update.message.reply_text(
        "*Comandos*\n"
        "/start — boas-vindas\n"
        "/novo_alerta — criar alerta de aluguel (preço, bairros, nome)\n"
        "/meus_alertas — listar alertas (id, nome, ativo/pausado)\n"
        "/pausar_alerta [id] — pausar ou reativar\n"
        "/deletar_alerta [id] — apagar alerta\n"
        "/observar [url OLX] — monitorar preço do anúncio\n"
        "/watchlist — listar observados\n"
        "/remover [id] — tirar da watchlist\n"
        "/status — intervalos e próximas execuções\n"
        "/cancelar — cancelar wizard\n\n"
        "Alertas disparam quando aparece anúncio novo nos filtros. "
        "Watchlist avisa mudança de preço ou remoção.",
        parse_mode=ParseMode.MARKDOWN,
    )
