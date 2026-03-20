"""
WIZARD do comando /novo_alerta.

ConversationHandler = máquina de estados:
  cada "estado" (WIZ_NAME, WIZ_PROPERTY, ...) espera um tipo de input.
  A função retorna o PRÓXIMO estado (número) ou ConversationHandler.END para sair.

range(9) gera 0,1,...,8 — só precisamos de IDs únicos para os estados.
"""
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
from database import crud
from scraper.olx_scraper import extract_olx_id_from_url

logger = logging.getLogger(__name__)

(
    WIZ_NAME,
    WIZ_PROPERTY,
    WIZ_TRANSACTION,
    WIZ_PRICE_MIN,
    WIZ_PRICE_MAX,
    WIZ_BEDROOMS,
    WIZ_AREA_MIN,
    WIZ_AREA_MAX,
    WIZ_NEIGHBORHOODS,
) = range(9)


def _session(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data["session_factory"]()


async def novo_alerta_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # user_data = dicionário por usuário — guardamos o progresso do wizard aqui
    context.user_data["wizard_alert"] = {"neighborhoods_selected": set()}
    await update.message.reply_text(
        "🆕 *Novo alerta*\n\n"
        "Digite um *nome* para este alerta (ex.: Centro/Pajuçara):",
        parse_mode="Markdown",
    )
    return WIZ_NAME


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
        "Digite um *nome* para este alerta (ex.: Centro/Pajuçara):",
        parse_mode="Markdown",
    )
    return WIZ_NAME


async def wiz_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = (update.message.text or "").strip()[:200]
    if not name:
        await update.message.reply_text("Nome inválido. Tente de novo.")
        return WIZ_NAME  # fica no mesmo estado até acertar
    context.user_data["wizard_alert"]["name"] = name
    await update.message.reply_text(
        "Tipo de imóvel:",
        reply_markup=keyboards.property_type_keyboard(),
    )
    return WIZ_PROPERTY


async def wiz_property_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # callback_query = clique em botão inline
    q = update.callback_query
    await q.answer()  # tira o "relógio" do botão no cliente Telegram
    key = q.data.replace("wiz_pt_", "")
    context.user_data["wizard_alert"]["property_type"] = key
    await q.edit_message_text(
        "Transação:",
        reply_markup=keyboards.transaction_keyboard(),
    )
    return WIZ_TRANSACTION


async def wiz_transaction_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    key = q.data.replace("wiz_tr_", "")
    context.user_data["wizard_alert"]["transaction"] = key
    await q.edit_message_text(
        "Preço *mínimo* (R$, só número) ou envie *Pular*:",
        parse_mode="Markdown",
    )
    return WIZ_PRICE_MIN


async def wiz_price_min(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip().lower()
    if text == "pular":
        context.user_data["wizard_alert"]["price_min"] = None
    else:
        try:
            # re.sub(r"\D", "", text) = só dígitos (tira R$, pontos, etc.)
            context.user_data["wizard_alert"]["price_min"] = int(re.sub(r"\D", "", text) or 0)
        except Exception:
            await update.message.reply_text("Número inválido. Ex.: 150000")
            return WIZ_PRICE_MIN
    await update.message.reply_text("Preço *máximo* (R$) ou *Pular*:", parse_mode="Markdown")
    return WIZ_PRICE_MAX


async def wiz_price_max(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip().lower()
    if text == "pular":
        context.user_data["wizard_alert"]["price_max"] = None
    else:
        try:
            context.user_data["wizard_alert"]["price_max"] = int(re.sub(r"\D", "", text) or 0)
        except Exception:
            await update.message.reply_text("Número inválido.")
            return WIZ_PRICE_MAX
    await update.message.reply_text("Mínimo de *quartos* (número) ou *Pular*:", parse_mode="Markdown")
    return WIZ_BEDROOMS


async def wiz_bedrooms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip().lower()
    if text == "pular":
        context.user_data["wizard_alert"]["bedrooms_min"] = None
    else:
        try:
            context.user_data["wizard_alert"]["bedrooms_min"] = int(text)
        except ValueError:
            await update.message.reply_text("Digite um número ou Pular.")
            return WIZ_BEDROOMS
    await update.message.reply_text("Área útil *mínima* (m²) ou *Pular*:", parse_mode="Markdown")
    return WIZ_AREA_MIN


async def wiz_area_min(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip().lower()
    if text == "pular":
        context.user_data["wizard_alert"]["area_min"] = None
    else:
        try:
            context.user_data["wizard_alert"]["area_min"] = float(text.replace(",", "."))
        except ValueError:
            await update.message.reply_text("Número inválido.")
            return WIZ_AREA_MIN
    await update.message.reply_text("Área *máxima* (m²) ou *Pular*:", parse_mode="Markdown")
    return WIZ_AREA_MAX


async def wiz_area_max(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip().lower()
    if text == "pular":
        context.user_data["wizard_alert"]["area_max"] = None
    else:
        try:
            context.user_data["wizard_alert"]["area_max"] = float(text.replace(",", "."))
        except ValueError:
            await update.message.reply_text("Número inválido.")
            return WIZ_AREA_MAX
    sel = context.user_data["wizard_alert"].get("neighborhoods_selected") or set()
    await update.message.reply_text(
        "Selecione os *bairros* (toque para marcar). Depois: Concluir.\n"
        "Se não quiser filtrar por bairro, conclua sem marcar.",
        parse_mode="Markdown",
        reply_markup=keyboards.neighborhoods_keyboard(sel),
    )
    return WIZ_NEIGHBORHOODS


async def wiz_neighborhoods_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    w = context.user_data.setdefault("wizard_alert", {})
    sel = w.setdefault("neighborhoods_selected", set())
    if data == "nbd_done":
        # Monta o dict que o scraper vai usar na URL do OLX
        filters_dict = {
            "property_type": w.get("property_type", "apartment"),
            "transaction": w.get("transaction", "sale"),
            "price_min": w.get("price_min"),
            "price_max": w.get("price_max"),
            "bedrooms_min": w.get("bedrooms_min"),
            "area_min": w.get("area_min"),
            "area_max": w.get("area_max"),
            "neighborhoods": sorted(sel),
        }
        async with _session(context) as session:
            user = await crud.get_or_create_user(
                session, update.effective_user.id, update.effective_user.username
            )
            alert = await crud.create_alert(session, user.id, w["name"], filters_dict)
        await q.edit_message_text(
            f"✅ Alerta *{alert.name}* criado (id `{alert.id}`).\n"
            f"Verificações a cada {context.application.bot_data.get('alert_min', 30)} min.",
            parse_mode="Markdown",
        )
        context.user_data.pop("wizard_alert", None)
        return ConversationHandler.END
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
            WIZ_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, wiz_name)],
            WIZ_PROPERTY: [CallbackQueryHandler(wiz_property_cb, pattern=r"^wiz_pt_")],
            WIZ_TRANSACTION: [CallbackQueryHandler(wiz_transaction_cb, pattern=r"^wiz_tr_")],
            WIZ_PRICE_MIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, wiz_price_min)],
            WIZ_PRICE_MAX: [MessageHandler(filters.TEXT & ~filters.COMMAND, wiz_price_max)],
            WIZ_BEDROOMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, wiz_bedrooms)],
            WIZ_AREA_MIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, wiz_area_min)],
            WIZ_AREA_MAX: [MessageHandler(filters.TEXT & ~filters.COMMAND, wiz_area_max)],
            WIZ_NEIGHBORHOODS: [
                CallbackQueryHandler(wiz_neighborhoods_cb, pattern=r"^nbd_")
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancel_wiz)],
        name="novo_alerta_wiz",
        persistent=False,
    )
