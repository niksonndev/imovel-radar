"""Wizard /novo_alerta."""
import logging
import re
from typing import Any

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
    context.user_data["wizard_alert"] = {"neighborhoods_selected": set()}
    await update.message.reply_text(
        "🆕 *Novo alerta*\n\n"
        "Digite um *nome* para este alerta (ex.: Centro/Pajuçara):",
        parse_mode="Markdown",
    )
    return WIZ_NAME


async def wiz_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = (update.message.text or "").strip()[:200]
    if not name:
        await update.message.reply_text("Nome inválido. Tente de novo.")
        return WIZ_NAME
    context.user_data["wizard_alert"]["name"] = name
    await update.message.reply_text(
        "Tipo de imóvel:",
        reply_markup=keyboards.property_type_keyboard(),
    )
    return WIZ_PROPERTY


async def wiz_property_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
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
        filters_dict = {
            "property_type": w.get("property_type", "apartment"),
            "transaction": w.get("transaction", "sale"),
            "price_min": w.get("price_min"),
            "price_max": w.get("price_max"),
            "bedrooms_min": w.get("bedrooms_min"),
            "area_min": w.get("area_min"),
            "area_max": w.get("area_max"),
            "neighborhoods": list(sel),
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


def conversation_novo_alerta() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("novo_alerta", novo_alerta_entry)],
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
