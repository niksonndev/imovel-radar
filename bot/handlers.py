"""
HANDLERS = uma função por COMANDO do Telegram (/start, /observar, ...).

Quando alguém manda /start, a lib chama cmd_start(update, context).
- update = dados da mensagem (quem mandou, texto, etc.)
- context = acesso ao bot_data, args do comando, etc.

async def = a função pode usar await (responder no Telegram, banco, OLX).
"""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot import keyboards
from database import crud
from scraper.olx_scraper import extract_olx_id_from_url

logger = logging.getLogger(__name__)


def _session(context: ContextTypes.DEFAULT_TYPE):
    """Abre uma sessão de banco (use com 'async with _session(context) as session:')."""
    return context.application.bot_data["session_factory"]()


def _fmt_money(v: float | None) -> str:
    """Formata número como moeda BR (troca ponto/vírgula)."""
    if v is None:
        return "—"
    return f"R$ {v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # /start também funciona como "reset geral" de estado da conversa.
    context.user_data.clear()

    # Garante linha no banco para esse usuário do Telegram
    async with _session(context) as session:
        await crud.get_or_create_user(
            session, update.effective_user.id, update.effective_user.username
        )
    await update.message.reply_text(
        "👋 *Olá!* Sou o bot de alertas OLX — *Maceió/AL*.\n\n",
        parse_mode="Markdown",
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def menu_home_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra o menu principal sem depender de /start."""
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(
        "🏠 *Menu principal*\nEscolha uma opção:",
        parse_mode="Markdown",
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def menu_meus_alertas_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback do botão '📋 Meus Alertas' com ações inline."""
    q = update.callback_query
    await q.answer()

    async with _session(context) as session:
        user = await crud.get_or_create_user(
            session, q.from_user.id, q.from_user.username
        )
        alerts = await crud.list_alerts(session, user.id)

    if not alerts:
        await q.message.reply_text(
            "Nenhum alerta criado ainda.",
            reply_markup=keyboards.home_keyboard(),
        )
        return

    for a in alerts:
        st = "▶️ ativo" if a.is_active else "⏸ pausado"
        action_label = "⏸ Pausar" if a.is_active else "▶️ Reativar"
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(action_label, callback_data=f"alert_toggle_{a.id}"),
                    InlineKeyboardButton("🗑 Deletar", callback_data=f"alert_delete_{a.id}"),
                ],
                [InlineKeyboardButton("🏠 Menu principal", callback_data="menu_home")],
            ]
        )
        await q.message.reply_text(
            f"• `id {a.id}` — *{a.name}* ({st})",
            parse_mode="Markdown",
            reply_markup=kb,
        )


async def alert_toggle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    try:
        aid = int(data.rsplit("_", 1)[-1])
    except ValueError:
        await q.message.reply_text("ID de alerta inválido.", reply_markup=keyboards.home_keyboard())
        return

    async with _session(context) as session:
        user = await crud.get_or_create_user(session, q.from_user.id, q.from_user.username)
        active = await crud.toggle_alert_active(session, aid, user.id)
    if active is None:
        await q.message.reply_text("Alerta não encontrado.", reply_markup=keyboards.home_keyboard())
        return
    await q.message.reply_text(
        "✅ Alerta agora está *" + ("ativo" if active else "pausado") + "*.",
        parse_mode="Markdown",
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def alert_delete_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    try:
        aid = int(data.rsplit("_", 1)[-1])
    except ValueError:
        await q.message.reply_text("ID de alerta inválido.", reply_markup=keyboards.home_keyboard())
        return

    async with _session(context) as session:
        user = await crud.get_or_create_user(session, q.from_user.id, q.from_user.username)
        ok = await crud.delete_alert(session, aid, user.id)

    await q.message.reply_text(
        "🗑 Alerta removido." if ok else "Alerta não encontrado.",
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def menu_ajuda_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback do botão '❓ Ajuda' (manda texto de comandos)."""
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(
        "*Como usar sem digitar comandos*\n\n"
        "Use os botões do menu principal para criar e gerenciar alertas, "
        "acompanhar anúncios, abrir watchlist e ver status.\n\n"
        "Você pode voltar ao menu principal pelos botões em cada tela.",
        parse_mode="Markdown",
        reply_markup=keyboards.home_keyboard(),
    )


async def menu_watchlist_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    async with _session(context) as session:
        user = await crud.get_or_create_user(session, q.from_user.id, q.from_user.username)
        items = await crud.list_watched(session, user.id)

    if not items:
        await q.message.reply_text("Watchlist vazia.", reply_markup=keyboards.home_keyboard())
        return

    for w in items:
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🗑 Remover", callback_data=f"watch_remove_{w.id}")],
                [InlineKeyboardButton("🏠 Menu principal", callback_data="menu_home")],
            ]
        )
        await q.message.reply_text(
            f"• `id {w.id}` — {w.title or 'Anúncio'}\n"
            f"  {_fmt_money(w.current_price)} — [link]({w.url})",
            parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=kb,
        )


async def watch_remove_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    try:
        wid = int(data.rsplit("_", 1)[-1])
    except ValueError:
        await q.message.reply_text("ID da watchlist inválido.", reply_markup=keyboards.home_keyboard())
        return
    async with _session(context) as session:
        user = await crud.get_or_create_user(session, q.from_user.id, q.from_user.username)
        ok = await crud.remove_watched(session, wid, user.id)
    await q.message.reply_text(
        "✅ Removido da watchlist." if ok else "Item não encontrado.",
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def menu_status_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    am = context.application.bot_data.get("alert_min", 30)
    wh = context.application.bot_data.get("watch_hours", 6)
    next_a = context.application.bot_data.get("next_alert_run")
    next_w = context.application.bot_data.get("next_watch_run")
    na = next_a.strftime("%d/%m %H:%M") if next_a else "—"
    nw = next_w.strftime("%d/%m %H:%M") if next_w else "—"
    await q.message.reply_text(
        f"*Status*\n"
        f"• Alertas: a cada *{am}* min (próx.: _{na}_)\n"
        f"• Watchlist: a cada *{wh}* h (próx.: _{nw}_)\n"
        f"• Região: Maceió/AL",
        parse_mode="Markdown",
        reply_markup=keyboards.home_keyboard(),
    )


async def cmd_meus_alertas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with _session(context) as session:
        user = await crud.get_or_create_user(
            session, update.effective_user.id, update.effective_user.username
        )
        alerts = await crud.list_alerts(session, user.id)
    if not alerts:
        await update.message.reply_text("Nenhum alerta. Use /novo_alerta")
        return
    lines = []
    for a in alerts:
        st = "▶️ ativo" if a.is_active else "⏸ pausado"
        lines.append(f"• `id {a.id}` — *{a.name}* ({st})")
    await update.message.reply_text(
        "*Seus alertas*\n" + "\n".join(lines), parse_mode="Markdown"
    )


async def cmd_pausar_alerta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # context.args = palavras depois do comando: /pausar_alerta 3 → ["3"]
    args = context.args or []
    if not args:
        await update.message.reply_text("Uso: `/pausar_alerta [id]`", parse_mode="Markdown")
        return
    try:
        aid = int(args[0])
    except ValueError:
        await update.message.reply_text("ID inválido.")
        return
    async with _session(context) as session:
        user = await crud.get_or_create_user(
            session, update.effective_user.id, update.effective_user.username
        )
        active = await crud.toggle_alert_active(session, aid, user.id)
    if active is None:
        await update.message.reply_text("Alerta não encontrado.")
        return
    await update.message.reply_text(
        "Alerta agora está *" + ("ativo" if active else "pausado") + "*.",
        parse_mode="Markdown",
    )


async def cmd_deletar_alerta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    if not args:
        await update.message.reply_text("Uso: `/deletar_alerta [id]`")
        return
    try:
        aid = int(args[0])
    except ValueError:
        await update.message.reply_text("ID inválido.")
        return
    async with _session(context) as session:
        user = await crud.get_or_create_user(
            session, update.effective_user.id, update.effective_user.username
        )
        ok = await crud.delete_alert(session, aid, user.id)
    await update.message.reply_text("Removido." if ok else "Não encontrado.")


async def cmd_observar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /observar https://... → baixa a página do anúncio, lê preço/título,
    salva na watchlist para o job periódico comparar depois.
    """
    args = context.args or []
    url = " ".join(args).strip()
    if not url or "olx.com.br" not in url.lower():
        await update.message.reply_text(
            "Uso: `/observar https://www.olx.com.br/d/...`", parse_mode="Markdown"
        )
        return
    oid = extract_olx_id_from_url(url)
    if not oid:
        await update.message.reply_text("Não consegui extrair o ID do anúncio na URL.")
        return
    scraper = context.application.bot_data["scraper"]
    try:
        info = await scraper.fetch_listing(url)
    except Exception as e:
        logger.exception(e)
        await update.message.reply_text("Erro ao ler o anúncio. Tente de novo mais tarde.")
        return
    if info.get("removed") or info.get("not_found"):
        await update.message.reply_text("Anúncio indisponível ou removido.")
        return
    async with _session(context) as session:
        user = await crud.get_or_create_user(
            session, update.effective_user.id, update.effective_user.username
        )
        await crud.add_watched(
            session,
            user.id,
            oid,
            url.split("?")[0],
            info.get("title"),
            info.get("price"),
        )
    await update.message.reply_text(
        f"✅ Na watchlist. Preço atual: {_fmt_money(info.get('price'))}",
        parse_mode="Markdown",
    )


async def cmd_watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with _session(context) as session:
        user = await crud.get_or_create_user(
            session, update.effective_user.id, update.effective_user.username
        )
        items = await crud.list_watched(session, user.id)
    if not items:
        await update.message.reply_text("Watchlist vazia. `/observar [url]`", parse_mode="Markdown")
        return
    lines = []
    for w in items:
        lines.append(
            f"• `id {w.id}` — {w.title or 'Anúncio'}\n"
            f"  {_fmt_money(w.current_price)} — [link]({w.url})"
        )
    await update.message.reply_text(
        "*Watchlist*\n" + "\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True
    )


async def cmd_remover(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    if not args:
        await update.message.reply_text("Uso: `/remover [id]` (id da watchlist)")
        return
    try:
        wid = int(args[0])
    except ValueError:
        await update.message.reply_text("ID inválido.")
        return
    async with _session(context) as session:
        user = await crud.get_or_create_user(
            session, update.effective_user.id, update.effective_user.username
        )
        ok = await crud.remove_watched(session, wid, user.id)
    await update.message.reply_text("Removido da watchlist." if ok else "Item não encontrado.")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Horários que o scheduler atualizou em bot_data (próxima janela aproximada)
    am = context.application.bot_data.get("alert_min", 30)
    wh = context.application.bot_data.get("watch_hours", 6)
    next_a = context.application.bot_data.get("next_alert_run")
    next_w = context.application.bot_data.get("next_watch_run")
    na = next_a.strftime("%d/%m %H:%M") if next_a else "—"
    nw = next_w.strftime("%d/%m %H:%M") if next_w else "—"
    await update.message.reply_text(
        f"*Status*\n"
        f"• Alertas: a cada *{am}* min (próx.: _{na}_)\n"
        f"• Watchlist: a cada *{wh}* h (próx.: _{nw}_)\n"
        f"• Região: Maceió/AL",
        parse_mode="Markdown",
    )


async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "*Comandos*\n"
        "/start — boas-vindas\n"
        "/novo_alerta — criar alerta (aluguel/venda, preço, bairros, nome)\n"
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
        parse_mode="Markdown",
    )
