"""
WIZARD do comando /novo_alerta.

ConversationHandler = máquina de estados:
  cada "estado" (WIZ_PROPERTY, WIZ_TRANSACTION, ...) espera um tipo de input.
  A função retorna o PRÓXIMO estado (número) ou ConversationHandler.END para sair.

range(10) gera 0,1,...,9 — só precisamos de IDs únicos para os estados.
"""
import asyncio
import logging
import re

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot import keyboards
from bot.carousel import immediate_seed
from database import crud
from scraper.olx_scraper import extract_olx_id_from_url

logger = logging.getLogger(__name__)

(
    WIZ_PROPERTY,
    WIZ_TRANSACTION,
    WIZ_PRICE_MIN,
    WIZ_PRICE_MAX,
    WIZ_NEIGHBORHOODS,
    WIZ_BEDROOMS,
    WIZ_AREA_MIN,
    WIZ_AREA_MAX,
    WIZ_CONFIRM,
    WIZ_NAME,
) = range(10)


def _session(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data["session_factory"]()


async def novo_alerta_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # user_data = dicionário por usuário — guardamos o progresso do wizard aqui
    context.user_data["wizard_alert"] = {"neighborhoods_selected": set()}
    await update.message.reply_text(
        "🆕 *Novo alerta*\n\n"
        "Tipo:\nAluguel ou Venda",
        parse_mode="Markdown",
        reply_markup=keyboards.transaction_keyboard(),
    )
    return WIZ_TRANSACTION


async def novo_alerta_entry_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Entrada do wizard iniciada via clique no menu.
    A diferença é que aqui o update vem como callback_query (não update.message).
    """
    q = update.callback_query
    await q.answer()
    context.user_data["wizard_alert"] = {"neighborhoods_selected": set()}
    await q.message.reply_text(
        "🆕 *Novo alerta*\n\n"
        "Tipo:\nAluguel ou Venda",
        parse_mode="Markdown",
        reply_markup=keyboards.transaction_keyboard(),
    )
    return WIZ_TRANSACTION


async def wiz_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    w = context.user_data.get("wizard_alert") or {}
    name = (update.message.text or "").strip()[:200]
    if not name:
        await update.message.reply_text("Nome inválido. Tente de novo.")
        return WIZ_NAME  # fica no mesmo estado até acertar

    if not w:
        await update.message.reply_text("Sessão do wizard expirada. Use /novo_alerta novamente.")
        return ConversationHandler.END

    w["name"] = name

    tr_label = {"sale": "Venda", "rent": "Aluguel"}.get(w.get("transaction"), w.get("transaction"))

    sel = w.get("neighborhoods_selected") or set()
    nb_s = ", ".join(sorted(sel)) if sel else "Qualquer bairro"

    pmin = w.get("price_min")
    pmax = w.get("price_max")
    if pmin is None and pmax is not None:
        price_s = f"Até {_fmt_money(pmax)}"
    elif pmin is not None and pmax is None:
        price_s = f"A partir de {_fmt_money(pmin)}"
    else:
        price_s = f"{_fmt_money(pmin)} - {_fmt_money(pmax)}"

    summary = (
        "🧾 *Confirmação do alerta*\n\n"
        f"💳 *Tipo:* {tr_label}\n"
        f"💰 *Preço:* {price_s}\n"
        f"📍 *Bairros:* {nb_s}\n"
        f"📝 *Nome:* `{name}`\n\n"
        "Confirme abaixo:"
    )

    await update.message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=keyboards.alert_confirmation_keyboard(),
    )
    return WIZ_CONFIRM


async def wiz_property_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # callback_query = clique em botão inline
    q = update.callback_query
    await q.answer()  # tira o "relógio" do botão no cliente Telegram
    key = q.data.replace("wiz_pt_", "")
    context.user_data["wizard_alert"]["property_type"] = key
    await q.edit_message_text(
        "Aluguel ou Venda:",
        reply_markup=keyboards.transaction_keyboard(),
    )
    return WIZ_TRANSACTION


async def wiz_transaction_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    key = q.data.replace("wiz_tr_", "")
    context.user_data["wizard_alert"]["transaction"] = key
    await q.edit_message_text(
        "Faixa de preço:\n\nSelecione uma opção (ou use *Personalizado*).",
        parse_mode="Markdown",
        reply_markup=keyboards.price_range_keyboard(key),
    )
    return WIZ_PRICE_MIN


async def wiz_price_preset_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Callback dos botões de faixa comum e de "Personalizado".

    Presets são gerados por keyboards.price_range_keyboard() com callback_data:
      - wiz_price_preset_<rent|sale>_<idx>
      - wiz_price_custom
    """
    q = update.callback_query
    await q.answer()

    data = q.data or ""
    w = context.user_data.setdefault("wizard_alert", {})
    tr = w.get("transaction") or "sale"

    if data == "wiz_price_custom":
        await q.message.reply_text(
            "Personalizado: envie o *preço mínimo* (R$, só número).",
            parse_mode="Markdown",
        )
        return WIZ_PRICE_MIN

    if not data.startswith("wiz_price_preset_"):
        return WIZ_PRICE_MIN

    # Ex.: wiz_price_preset_rent_1
    parts = data.split("_")
    if len(parts) < 5:
        return WIZ_PRICE_MIN

    preset_tr = parts[-2]
    try:
        idx = int(parts[-1])
    except ValueError:
        idx = -1

    preset_map = {
        "rent": {
            0: (None, 800),
            1: (800, 1500),
            2: (1500, 3000),
            3: (3000, None),
        },
        "sale": {
            0: (None, 150000),
            1: (150000, 300000),
            2: (300000, 600000),
            3: (600000, None),
        },
    }

    if preset_tr not in preset_map or idx not in preset_map[preset_tr]:
        return WIZ_PRICE_MIN

    pmin, pmax = preset_map[preset_tr][idx]
    w["price_min"] = pmin
    w["price_max"] = pmax

    sel = w.get("neighborhoods_selected") or set()
    await q.message.reply_text(
        "Selecione os *bairros* (toque para marcar). Depois: Concluir.",
        parse_mode="Markdown",
        reply_markup=keyboards.neighborhoods_keyboard(sel),
    )
    return WIZ_NEIGHBORHOODS


async def wiz_price_min(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip().lower()
    try:
        # re.sub(r"\D", "", text) = só dígitos (tira R$, pontos, etc.)
        price_min = int(re.sub(r"\D", "", text) or 0)
    except Exception:
        price_min = 0
    if price_min <= 0:
        await update.message.reply_text("Número inválido. Ex.: 150000")
        return WIZ_PRICE_MIN

    context.user_data["wizard_alert"]["price_min"] = price_min
    await update.message.reply_text("Preço *máximo* (R$):", parse_mode="Markdown")
    return WIZ_PRICE_MAX


async def wiz_price_max(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip().lower()
    try:
        price_max = int(re.sub(r"\D", "", text) or 0)
    except Exception:
        price_max = 0
    if price_max <= 0:
        await update.message.reply_text("Número inválido.")
        return WIZ_PRICE_MAX

    context.user_data["wizard_alert"]["price_max"] = price_max

    # Próximo passo: bairros (inline)
    sel = context.user_data["wizard_alert"].get("neighborhoods_selected") or set()
    await update.message.reply_text(
        "Selecione os *bairros* (toque para marcar). Depois: Concluir.\n"
        "Se não quiser filtrar por bairro, conclua sem marcar.",
        parse_mode="Markdown",
        reply_markup=keyboards.neighborhoods_keyboard(sel),
    )
    return WIZ_NEIGHBORHOODS


async def wiz_bedrooms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip().lower()
    w = context.user_data["wizard_alert"]
    if text == "pular":
        w["bedrooms_min"] = None
    else:
        try:
            bedrooms_min = int(re.sub(r"[^\d]", "", text) or 0)
        except Exception:
            bedrooms_min = 0
        if bedrooms_min <= 0:
            await update.message.reply_text("Digite um número de quartos válido ou toque em `Pular`.", parse_mode="Markdown")
            return WIZ_BEDROOMS
        w["bedrooms_min"] = bedrooms_min

    await update.message.reply_text(
        "Metragem (opcional)\n\n"
        "Área útil *mínima* (m²) ou toque em `Pular`:",
        parse_mode="Markdown",
        reply_markup=keyboards.skip_keyboard(),
    )
    return WIZ_AREA_MIN


async def wiz_area_min(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip().lower()
    w = context.user_data["wizard_alert"]
    if text == "pular":
        w["area_min"] = None
    else:
        try:
            area_min = float(text.replace(",", "."))
        except ValueError:
            await update.message.reply_text(
                "Número inválido. Envie um valor ou toque em `Pular`.",
                parse_mode="Markdown",
            )
            return WIZ_AREA_MIN
        if area_min <= 0:
            await update.message.reply_text(
                "A metragem mínima deve ser > 0.",
                parse_mode="Markdown",
            )
            return WIZ_AREA_MIN
        w["area_min"] = area_min

    await update.message.reply_text(
        "Área *máxima* (m²) ou toque em `Pular`:",
        parse_mode="Markdown",
        reply_markup=keyboards.skip_keyboard(),
    )
    return WIZ_AREA_MAX


async def wiz_area_max(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip().lower()
    w = context.user_data["wizard_alert"]
    if text == "pular":
        w["area_max"] = None
    else:
        try:
            area_max = float(text.replace(",", "."))
        except ValueError:
            await update.message.reply_text(
                "Número inválido. Envie um valor ou toque em `Pular`.",
                parse_mode="Markdown",
            )
            return WIZ_AREA_MAX
        if area_max <= 0:
            await update.message.reply_text(
                "A metragem máxima deve ser > 0.",
                parse_mode="Markdown",
            )
            return WIZ_AREA_MAX
        w["area_max"] = area_max

    # Confirmação: envia um resumo antes de salvar.
    prop_map = dict(keyboards.PROPERTY_TYPES)
    tr_label = {"sale": "Venda", "rent": "Aluguel"}.get(w.get("transaction"), w.get("transaction"))
    prop_label = prop_map.get(w.get("property_type"), w.get("property_type"))

    sel = w.get("neighborhoods_selected") or set()
    nb_s = ", ".join(sorted(sel)) if sel else "Qualquer bairro"

    bedrooms = w.get("bedrooms_min")
    bed_s = "Qualquer" if bedrooms is None else f">= {bedrooms} quartos"

    area_min = w.get("area_min")
    area_max = w.get("area_max")
    if area_min is None and area_max is None:
        area_s = "Qualquer"
    else:
        parts: list[str] = []
        if area_min is not None:
            parts.append(f">= {area_min:g}m²")
        if area_max is not None:
            parts.append(f"<= {area_max:g}m²")
        area_s = " | ".join(parts)

    pmin = w.get("price_min")
    pmax = w.get("price_max")
    price_s = f"{_fmt_money(pmin)} - {_fmt_money(pmax)}"

    summary = (
        "🧾 *Confirmação do alerta*\n\n"
        f"🏠 *Tipo:* {prop_label}\n"
        f"💳 *Transação:* {tr_label}\n"
        f"💰 *Preço:* {price_s}\n"
        f"📍 *Bairros:* {nb_s}\n"
        f"🛏 *Quartos:* {bed_s}\n"
        f"📐 *Metragem:* {area_s}\n\n"
        "Se estiver tudo certo, confirme abaixo. O *nome do alerta* vem na próxima etapa."
    )

    await update.message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=keyboards.alert_confirmation_keyboard(),
    )
    return WIZ_CONFIRM


async def wiz_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()

    data = q.data or ""
    w = context.user_data.get("wizard_alert") or {}

    if data == "wiz_confirm_no":
        context.user_data.pop("wizard_alert", None)
        await q.message.reply_text("Ok! O alerta não foi salvo.")
        return ConversationHandler.END

    if data != "wiz_confirm_yes":
        return WIZ_CONFIRM

    name = w.get("name")
    if not name:
        context.user_data.pop("wizard_alert", None)
        await q.message.reply_text("Nome do alerta ausente. Tente novamente com /novo_alerta.")
        return ConversationHandler.END

    sel = w.get("neighborhoods_selected") or set()
    filters_dict = {
        "transaction": w.get("transaction", "sale"),
        "price_min": w.get("price_min"),
        "price_max": w.get("price_max"),
        "neighborhoods": sorted(sel),
    }

    await q.message.reply_text("⏳ Peraê, tô procurando imóveis pra você...")

    async with _session(context) as session:
        user = await crud.get_or_create_user(
            session, update.effective_user.id, update.effective_user.username
        )
        alert = await crud.create_alert(session, user.id, name, filters_dict)

    context.user_data.pop("wizard_alert", None)

    task = asyncio.create_task(
        immediate_seed(
            context.application,
            alert.id,
            update.effective_user.id,
            filters_dict,
            context.user_data,
        )
    )
    context.user_data[f"_seed_task_{alert.id}"] = task

    return ConversationHandler.END


async def wiz_neighborhoods_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    w = context.user_data.setdefault("wizard_alert", {})
    sel = w.setdefault("neighborhoods_selected", set())
    if data == "nbd_done":
        await q.message.reply_text(
            "Agora, envie o *nome do alerta* (ex.: `Aluguel Centro`).",
            parse_mode="Markdown",
        )
        return WIZ_NAME
    if data.startswith("nbd_"):
        name = data[4:]
        if name in sel:
            sel.discard(name)
        else:
            sel.add(name)
        await q.edit_message_reply_markup(reply_markup=keyboards.neighborhoods_keyboard(sel))
    return WIZ_NEIGHBORHOODS


async def cancel_wiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("wizard_alert", None)
    await update.message.reply_text("Wizard cancelado.")
    return ConversationHandler.END


# ---------------- ACOMPANHAR ANUNCIO (watchlist) ----------------


(ACOMP_URL,) = range(1)


def _fmt_money(v: float | None) -> str:
    if v is None:
        return "—"
    return f"R$ {v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


async def acompanhar_entry_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entrada da conversa quando o usuário clica em 'Acompanhar Anúncio' no menu."""
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(
        "👁 Envie a *URL do anúncio OLX* que você quer acompanhar.\n\n"
        "Ex.: `https://www.olx.com.br/d/...`",
        parse_mode="Markdown",
    )
    return ACOMP_URL


async def acompanhar_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recebe a URL digitada e chama a mesma lógica de /observar para salvar na watchlist."""
    url = (update.message.text or "").strip()
    if not url or "olx.com.br" not in url.lower():
        await update.message.reply_text(
            "URL inválida. Envie uma URL do OLX (ex.: https://www.olx.com.br/d/...).",
            parse_mode="Markdown",
        )
        return ACOMP_URL

    oid = extract_olx_id_from_url(url)
    if not oid:
        await update.message.reply_text("Não consegui extrair o ID do anúncio pela URL.")
        return ACOMP_URL

    scraper = context.application.bot_data["scraper"]
    try:
        info = await scraper.fetch_listing(url)
    except Exception:
        await update.message.reply_text("Erro ao ler o anúncio. Tente de novo mais tarde.")
        return ACOMP_URL

    if info.get("removed") or info.get("not_found"):
        await update.message.reply_text("Anúncio indisponível ou removido.")
        return ConversationHandler.END

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
    return ConversationHandler.END


async def cancel_acompanhar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Acompanhar Anúncio cancelado.")
    return ConversationHandler.END


def conversation_acompanhar_anuncio() -> ConversationHandler:
    """Conversa curta: pede URL e adiciona na watchlist."""
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(acompanhar_entry_cb, pattern=r"^menu_acompanhar$")],
        states={
            ACOMP_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, acompanhar_url)
            ]
        },
        fallbacks=[CommandHandler("cancelar", cancel_acompanhar)],
        name="acompanhar_anuncio",
        persistent=False,
    )


def conversation_novo_alerta() -> ConversationHandler:
    """
    Registra o fluxo completo. filters.COMMAND = mensagens que começam com /
    (~filters.COMMAND) = aceita só texto que NÃO é comando.
    """
    return ConversationHandler(
        entry_points=[
            CommandHandler("novo_alerta", novo_alerta_entry),
            CallbackQueryHandler(novo_alerta_entry_cb, pattern=r"^menu_novo_alerta$"),
        ],
        states={
            WIZ_TRANSACTION: [
                CallbackQueryHandler(wiz_transaction_cb, pattern=r"^wiz_tr_")
            ],
            WIZ_PRICE_MIN: [
                CallbackQueryHandler(wiz_price_preset_cb, pattern=r"^wiz_price_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, wiz_price_min),
            ],
            WIZ_PRICE_MAX: [MessageHandler(filters.TEXT & ~filters.COMMAND, wiz_price_max)],
            WIZ_NEIGHBORHOODS: [CallbackQueryHandler(wiz_neighborhoods_cb, pattern=r"^nbd_")],
            WIZ_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, wiz_name)],
            WIZ_CONFIRM: [CallbackQueryHandler(wiz_confirm_cb, pattern=r"^wiz_confirm_")],
        },
        fallbacks=[CommandHandler("cancelar", cancel_wiz)],
        name="novo_alerta_wiz",
        persistent=False,
    )
