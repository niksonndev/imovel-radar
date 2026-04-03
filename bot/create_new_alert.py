"""Wizard de criação de alerta (/new_alert)."""

from __future__ import annotations

import logging
import re

from telegram import CallbackQuery, Message, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.carousel import immediate_seed
from bot.ui import keyboards, menus
from database import create_new_alert, get_connection

logger = logging.getLogger(__name__)


async def _start_new_alert(chat: Message, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["new_alert"] = {
        "step": "price",
        "alert_name": None,
        "min_price": None,
        "max_price": None,
        "neighbourhoods": [],
    }
    await chat.reply_text(
        menus.wizard_novo_alerta_intro(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.price_range_keyboard(),
    )


async def new_alert_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _start_new_alert(update.message, context)


async def new_alert_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    await _start_new_alert(update.callback_query.message, context)


def format_brl(v: float | None) -> str:
    if v is None:
        return "—"
    return f"R$ {v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _confirm_summary(*, price_s: str, nb_s: str, name: str) -> str:
    return (
        "🧾 *Alert confirmation*\n\n"
        f"💰 *Price:* {price_s}\n"
        f"📍 *Neighborhoods:* {nb_s}\n"
        f"📝 *Name:* `{name}`\n\n"
        "Confirm below:"
    )


async def wiz_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    w = context.user_data.get("new_alert")
    if w is None:
        await update.effective_message.reply_text(
            "Sua sessão expirou. Por favor, comece novamente usando /new_alert"
        )
        return

    name = (update.effective_message.text or "").strip()[:200]
    if not name:
        await update.effective_message.reply_text("Invalid name. Try again.")
        return

    w["alert_name"] = name
    w["step"] = "confirm"

    sel = w.get("neighbourhoods") or []
    nb_s = ", ".join(sorted(sel)) if sel else "Any neighborhood"

    pmin = w.get("min_price")
    pmax = w.get("max_price")
    if pmin is None and pmax is not None:
        price_s = f"Up to {format_brl(pmax)}"
    elif pmin is not None and pmax is None:
        price_s = f"From {format_brl(pmin)}"
    else:
        price_s = f"{format_brl(pmin)} – {format_brl(pmax)}"

    await update.effective_message.reply_text(
        _confirm_summary(price_s=price_s, nb_s=nb_s, name=name),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.alert_confirmation_keyboard(),
    )


async def _wiz_price_preset(
    q: CallbackQuery, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Callback dos botões de faixa comum e de "Personalizado"."""
    data = q.data or ""
    w = context.user_data.get("new_alert")
    if w is None:
        context.user_data.pop("new_alert", None)
        await q.message.reply_text(
            "Session expired. Use /new_alert again.",
        )
        return

    if data == "wiz_price_custom":
        await q.message.reply_text(
            "Custom: send the *minimum price* (BRL, digits only).",
            parse_mode=ParseMode.MARKDOWN,
        )
        w["step"] = "price"
        return

    if not data.startswith("wiz_price_preset_"):
        return

    parts = data.split("_")
    if len(parts) < 5:
        return

    preset_tr = parts[-2]
    try:
        idx = int(parts[-1])
    except ValueError:
        idx = -1

    preset_map = {
        0: (None, 800),
        1: (800, 1500),
        2: (1500, 3000),
        3: (3000, None),
    }

    if preset_tr != "rent" or idx not in preset_map:
        return

    pmin, pmax = preset_map[idx]
    w["min_price"] = pmin
    w["max_price"] = pmax

    sel = w.get("neighbourhoods") or []
    await q.message.reply_text(
        "Select *neighborhoods* (tap to toggle). Then tap Done.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.neighborhoods_keyboard(sel),
    )
    w["step"] = "pick"


async def wiz_price_preset_cb(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    q = update.callback_query
    if q is None:
        return
    await q.answer()
    await _wiz_price_preset(q, context)


async def _wiz_price_min(msg: Message, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lê e valida o preço mínimo informado no wizard."""
    w = context.user_data.get("new_alert")
    if w is None:
        context.user_data.pop("new_alert", None)
        await msg.reply_text(
            "Your wizard session expired. Use /new_alert again.",
        )
        return

    text = (msg.text or "").strip().lower()
    try:
        price_min = int(re.sub(r"\D", "", text) or 0)
    except Exception:
        price_min = 0
    if price_min <= 0:
        await msg.reply_text("Invalid number. Example: 150000")
        return

    w["min_price"] = price_min
    await msg.reply_text(
        "*Maximum* price (BRL):",
        parse_mode=ParseMode.MARKDOWN,
    )
    w["step"] = "price_max"


async def wiz_price_min(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return
    await _wiz_price_min(msg, context)


async def _wiz_price_max(msg: Message, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lê e valida o preço máximo antes de seguir para bairros."""
    w = context.user_data.get("new_alert")
    if w is None:
        context.user_data.pop("new_alert", None)
        await msg.reply_text(
            "Your wizard session expired. Use /new_alert again.",
        )
        return

    text = (msg.text or "").strip().lower()
    try:
        price_max = int(re.sub(r"\D", "", text) or 0)
    except Exception:
        price_max = 0
    if price_max <= 0:
        await msg.reply_text("Invalid number.")
        return

    p_min = w.get("min_price")
    if p_min is not None and price_max < p_min:
        await msg.reply_text("Maximum price must be greater than or equal to minimum.")
        return

    w["max_price"] = price_max

    sel = w.get("neighbourhoods") or []
    await msg.reply_text(
        "Select *neighborhoods* (tap to toggle). Then tap Done.\n"
        "To skip the filter, finish without selecting any.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.neighborhoods_keyboard(sel),
    )
    w["step"] = "pick"


async def wiz_price_max(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg is None:
        return
    await _wiz_price_max(msg, context)


async def _wiz_confirm(
    update: Update, q: CallbackQuery, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Confirma ou cancela o alerta e executa seed inicial."""
    data = q.data or ""
    w = context.user_data.get("new_alert")
    if w is None:
        context.user_data.pop("new_alert", None)
        await q.message.reply_text(
            "Session expired. Use /new_alert again.",
        )
        return

    if data == "wiz_confirm_no":
        context.user_data.pop("new_alert", None)
        await q.message.reply_text(
            "Okay — the alert was not saved.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return

    if data != "wiz_confirm_yes":
        return

    name = w.get("alert_name")
    if not name:
        context.user_data.pop("new_alert", None)
        await q.message.reply_text(
            "Alert name missing. Try again from the main menu.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return

    filters_dict = {
        "min_price": w.get("min_price"),
        "max_price": w.get("max_price"),
        "neighborhoods": sorted(w.get("neighbourhoods") or []),
    }

    user = update.effective_user
    if user is None:
        context.user_data.pop("new_alert", None)
        return

    conn = get_connection()
    try:
        alert_id = create_new_alert(conn, user.id, w)
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Failed to save new alert to the database.")
        await q.message.reply_text(
            "Could not save your alert right now. Try again shortly.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        context.user_data.pop("new_alert", None)
        return
    finally:
        conn.close()

    context.user_data.pop("new_alert", None)

    await q.message.reply_text("⏳ Looking for listings that match your filters…")
    await immediate_seed(
        context.application,
        alert_id,
        user.id,
        filters_dict,
        context.user_data,
    )


async def wiz_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if q is None:
        return
    await q.answer()
    await _wiz_confirm(update, q, context)


async def _wiz_neighborhoods(
    q: CallbackQuery, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Alterna seleção de bairros e avança quando usuário conclui."""
    data = q.data or ""
    w = context.user_data.get("new_alert")
    if w is None:
        context.user_data.pop("new_alert", None)
        await q.message.reply_text(
            "Session expired. Use /new_alert again.",
        )
        return

    sel: list[str] = w.setdefault("neighbourhoods", [])
    if data == "nbd_done":
        await q.message.reply_text(
            "Now send the *alert name* (e.g. `Downtown rent`).",
            parse_mode=ParseMode.MARKDOWN,
        )
        w["step"] = "name"
        return
    if data.startswith("nbd_"):
        nb = data[4:]
        if nb in sel:
            sel.remove(nb)
        else:
            sel.append(nb)
        await q.edit_message_reply_markup(
            reply_markup=keyboards.neighborhoods_keyboard(sel)
        )


async def wiz_neighborhoods_cb(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    q = update.callback_query
    if q is None:
        return
    await q.answer()
    await _wiz_neighborhoods(q, context)


async def cancel_wiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("new_alert", None)
    await update.effective_message.reply_text(
        "Alert creation cancelled.",
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def route_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "new_alert":
        await new_alert_cb(query.message, context)
