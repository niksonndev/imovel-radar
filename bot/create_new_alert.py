"""Wizard de criação de alerta (/novo_alerta)."""

from __future__ import annotations

import json
import logging
import re

from telegram import Update
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.carousel import immediate_seed
from bot.ui import keyboards, menus
from database import create_new_alert, ensure_user, get_connection
from database.queries import get_maceio_neighbourhoods
from utils.pricing import format_brl

logger = logging.getLogger(__name__)

(
    PRICE,
    NEIGHBOURHOODS,
    NAME,
    CONFIRM,
) = range(4)


async def _enter_neighbourhoods(msg, context) -> None:
    wizard = context.user_data["new_alert"]
    sel = wizard.get("neighbourhoods") or []
    conn = get_connection()
    try:
        nb_options = get_maceio_neighbourhoods(conn)
        wizard["nb_options"] = nb_options
    finally:
        conn.close()
    await msg.reply_text(
        "Selecione os *bairros* (toque para marcar). Toque em Concluir quando terminar.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.neighborhoods_keyboard(sel, nb_options),
    )


def _confirm_summary(*, price_s: str, nb_s: str, name: str) -> str:
    # ParseMode.MARKDOWN legado: escapa texto vindo do usuário / bairros (evita injeção de ênfase/links).
    esc_price = escape_markdown(price_s, version=1)
    esc_nb = escape_markdown(nb_s, version=1)
    esc_name = escape_markdown(name, version=1)
    return (
        "🧾 *Configuração do alerta*\n\n"
        f"💰 *Preço:* {esc_price}\n"
        f"📍 *Bairros:* {esc_nb}\n"
        f"📝 *Nome:* `{esc_name}`\n\n"
        "Confirme abaixo:"
    )


async def new_alert_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_alert"] = {
        "alert_name": None,
        "min_price": None,
        "max_price": None,
        "neighbourhoods": [],
    }
    await update.effective_message.reply_text(
        menus.wizard_novo_alerta_intro(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.price_range_keyboard(),
    )
    return PRICE


async def wiz_price_preset_cb(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    wizard = context.user_data.get("new_alert")
    if wizard is None:
        await query.message.reply_text("Sessão expirada. Use /novo_alerta novamente.")
        return ConversationHandler.END

    preset_map = {
        "wiz_price_preset_rent_0": (None, 800),
        "wiz_price_preset_rent_1": (800, 1500),
        "wiz_price_preset_rent_2": (1500, 3000),
        "wiz_price_preset_rent_3": (3000, None),
    }
    pmin, pmax = preset_map.get(query.data, (None, None))
    wizard["min_price"] = pmin
    wizard["max_price"] = pmax
    await _enter_neighbourhoods(query.message, context)
    return NEIGHBOURHOODS


async def wiz_price_custom_cb(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["new_alert"]["awaiting"] = "price_min"
    await query.message.reply_text("Digite o preço mínimo (só números):")
    return PRICE


async def wiz_price_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    wizard = context.user_data["new_alert"]
    value = int(re.sub(r"\D", "", update.message.text or "") or 0)
    if value <= 0:
        await update.message.reply_text("Número inválido, tente novamente.")
        return PRICE

    if wizard.get("awaiting") == "price_min":
        wizard["min_price"] = value
        wizard["awaiting"] = "price_max"
        await update.message.reply_text("Agora o preço máximo:")
        return PRICE

    # awaiting == "price_max"
    pmin = wizard.get("min_price")
    if isinstance(pmin, int) and value < pmin:
        await update.message.reply_text(
            "O preço máximo deve ser maior ou igual ao mínimo. Envie o máximo novamente:"
        )
        return PRICE

    wizard["max_price"] = value
    wizard.pop("awaiting", None)
    await _enter_neighbourhoods(update.message, context)
    return NEIGHBOURHOODS


async def wiz_neighbourhoods_cb(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    wizard = context.user_data["new_alert"]
    sel: list[str] = wizard.setdefault("neighbourhoods", [])

    if data == "nbd_done":
        wizard.pop("nb_options", None)
        await query.message.reply_text(
            "Agora envie o *nome do alerta* (ex: `Aluguel Jatiúca`).",
            parse_mode=ParseMode.MARKDOWN,
        )
        return NAME

    nb_options = wizard.get("nb_options") or []
    idx_s = data[4:]  # após "nbd_"
    try:
        idx = int(idx_s, 10)
    except ValueError:
        await query.answer("Seleção inválida.", show_alert=False)
        return NEIGHBOURHOODS
    if not (0 <= idx < len(nb_options)):
        await query.answer("Bairro inválido ou sessão desatualizada.", show_alert=False)
        return NEIGHBOURHOODS

    nb = nb_options[idx]
    if nb in sel:
        sel.remove(nb)
    else:
        sel.append(nb)

    await query.edit_message_reply_markup(
        reply_markup=keyboards.neighborhoods_keyboard(sel, nb_options)
    )
    return NEIGHBOURHOODS


async def wiz_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    wizard = context.user_data["new_alert"]

    name = (update.effective_message.text or "").strip()[:200]
    if not name:
        await update.effective_message.reply_text("Nome inválido, tente novamente.")
        return NAME

    wizard["alert_name"] = name

    sel = wizard.get("neighbourhoods") or []
    nb_s = ", ".join(sorted(sel)) if sel else "Qualquer bairro"

    pmin = wizard.get("min_price")
    pmax = wizard.get("max_price")
    if pmin is None:
        price_s = f"Até {format_brl(pmax)}"
    elif pmax is None:
        price_s = f"A partir de {format_brl(pmin)}"
    else:
        price_s = f"{format_brl(pmin)} – {format_brl(pmax)}"

    await update.effective_message.reply_text(
        _confirm_summary(price_s=price_s, nb_s=nb_s, name=name),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.alert_confirmation_keyboard(),
    )
    return CONFIRM


async def wiz_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    wizard = context.user_data["new_alert"]

    if query.data == "wiz_confirm_no":
        await query.message.reply_text(
            "Okay — alerta não salvo.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return ConversationHandler.END

    user = update.effective_user

    conn = get_connection()
    try:
        internal_user_id = ensure_user(conn, user.id)
        alert_data = {
            "user_id": internal_user_id,
            "alert_name": wizard["alert_name"],
            "min_price": wizard.get("min_price"),
            "max_price": wizard.get("max_price"),
            "neighbourhoods": json.dumps(wizard.get("neighbourhoods") or []),
        }
        alert_id = create_new_alert(conn, alert_data)
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Falha ao salvar usuário/alerta no banco.")
        await query.message.reply_text(
            "Não foi possível salvar o alerta. Tente novamente.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return ConversationHandler.END
    finally:
        conn.close()

    await query.message.reply_text("⏳ Procurando imóveis que combinam com seu alerta…")
    await immediate_seed(
        context.application,
        alert_id,
        user.id,
        context.user_data,
    )
    return ConversationHandler.END


async def cancel_wiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("new_alert", None)
    await update.effective_message.reply_text(
        "Criação do alerta cancelada.",
        reply_markup=keyboards.main_menu_keyboard(),
    )
    return ConversationHandler.END


def new_alert_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("novo_alerta", new_alert_cmd),
            CallbackQueryHandler(new_alert_cmd, pattern="^novo_alerta$"),
        ],
        states={
            PRICE: [
                CallbackQueryHandler(wiz_price_preset_cb, pattern="^wiz_price_preset_"),
                CallbackQueryHandler(wiz_price_custom_cb, pattern="^wiz_price_custom$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, wiz_price_text),
            ],
            NEIGHBOURHOODS: [
                CallbackQueryHandler(wiz_neighbourhoods_cb, pattern="^nbd_"),
            ],
            NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wiz_name),
            ],
            CONFIRM: [
                CallbackQueryHandler(wiz_confirm_cb, pattern="^wiz_confirm_"),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancel_wiz)],
    )
