"""Ponto único de entrada para CallbackQueryHandler."""

from __future__ import annotations

import logging
import re

from telegram import InputMediaPhoto, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.carousel import (
    PAGE_SIZE,
    _carousel_caption,
    _carousel_keyboard,
    _carousel_photo_url,
)
from bot.novo_alerta_wizard import (
    NEW_ALERT_STEP_KEY,
    WIZ_CONFIRM,
    WIZ_NEIGHBORHOODS,
    WIZ_PRICE_MIN,
    novo_alerta_entry_cb,
    wiz_confirm_cb,
    wiz_neighborhoods_cb,
    wiz_price_preset_cb,
)
from bot.ui import keyboards, menus

logger = logging.getLogger(__name__)


async def _menu_home_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(
        menus.menu_principal_inline(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def _menu_meus_alertas_cb(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(
        menus.meus_alertas_unavailable_inline(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.home_keyboard(),
    )


async def _alert_toggle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    try:
        int(data.rsplit("_", 1)[-1])
    except ValueError:
        await q.message.reply_text(
            menus.id_alerta_invalido(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.home_keyboard(),
        )
        return

    await q.message.reply_text(
        menus.alert_toggle_unavailable(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def _alert_delete_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    try:
        int(data.rsplit("_", 1)[-1])
    except ValueError:
        await q.message.reply_text(
            menus.id_alerta_invalido(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.home_keyboard(),
        )
        return

    await q.message.reply_text(
        menus.alert_delete_unavailable(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def _menu_ajuda_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(
        menus.ajuda_menu_inline(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.home_keyboard(),
    )


async def _menu_watchlist_cb(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(
        menus.watchlist_unavailable_inline(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.home_keyboard(),
    )


async def _watch_remove_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    try:
        int(data.rsplit("_", 1)[-1])
    except ValueError:
        await q.message.reply_text(
            menus.id_watchlist_invalido(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.home_keyboard(),
        )
        return

    await q.message.reply_text(
        menus.watch_remove_unavailable(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def _menu_status_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    watch_days = context.application.bot_data.get("watch_days", 1)
    next_a = context.application.bot_data.get("next_alert_run")
    next_w = context.application.bot_data.get("next_watch_run")
    na = next_a.strftime("%d/%m %H:%M") if next_a else "—"
    nw = next_w.strftime("%d/%m %H:%M") if next_w else "—"
    await q.message.reply_text(
        menus.status_menu(watch_days=watch_days, next_alert=na, next_watch=nw),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.home_keyboard(),
    )


async def _carousel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()

    data = q.data or ""
    parts = data.split("_")
    if len(parts) < 3:
        return

    action = parts[-1]
    carousel_id = "_".join(parts[1:-1])
    key = f"carousel_{carousel_id}"
    carousel = context.user_data.get(key)

    if not carousel:
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    ads = carousel["listings"]
    current_idx = carousel["index"]
    total = len(ads)

    page = current_idx // PAGE_SIZE
    page_start = page * PAGE_SIZE
    page_end = min(page_start + PAGE_SIZE, total)

    if action == "next":
        new_idx = min(current_idx + 1, page_end - 1)
    elif action == "prev":
        new_idx = max(current_idx - 1, page_start)
    elif action == "pgn":
        new_idx = min((page + 1) * PAGE_SIZE, total - 1)
    elif action == "pgp":
        new_idx = max((page - 1) * PAGE_SIZE, 0)
    else:
        return

    if new_idx == current_idx:
        return

    carousel["index"] = new_idx
    ad = ads[new_idx]

    caption = _carousel_caption(ad, new_idx, total)
    keyboard = _carousel_keyboard(carousel_id, new_idx, total, ad.get("url"))
    photo_url = _carousel_photo_url(ad)
    photo = photo_url is not None
    was_photo = carousel.get("is_photo", False)

    if photo and was_photo:
        try:
            await q.edit_message_media(
                media=InputMediaPhoto(media=photo_url, caption=caption),
                reply_markup=keyboard,
            )
            return
        except Exception as e:
            logger.warning("edit_message_media falhou: %s", e)

    if not photo and not was_photo:
        try:
            await q.edit_message_text(text=caption, reply_markup=keyboard)
            return
        except Exception as e:
            logger.warning("edit_message_text falhou: %s", e)

    chat_id = q.message.chat_id
    try:
        await q.message.delete()
    except Exception:
        pass

    if photo and photo_url:
        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo_url,
                caption=caption,
                reply_markup=keyboard,
            )
            carousel["is_photo"] = True
            return
        except Exception:
            pass

    await context.bot.send_message(chat_id=chat_id, text=caption, reply_markup=keyboard)
    carousel["is_photo"] = False


async def route_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Despacha callback_data para o handler adequado."""
    q = update.callback_query
    if q is None:
        return
    data = q.data or ""

    if data == "menu_home":
        await _menu_home_cb(update, context)
        return
    if data == "menu_meus_alertas":
        await _menu_meus_alertas_cb(update, context)
        return
    if data == "menu_ajuda":
        await _menu_ajuda_cb(update, context)
        return
    if data == "menu_watchlist":
        await _menu_watchlist_cb(update, context)
        return
    if data == "menu_status":
        await _menu_status_cb(update, context)
        return
    if data == "menu_novo_alerta":
        await novo_alerta_entry_cb(update, context)
        return

    if data.startswith("wiz_price_"):
        if context.user_data.get(NEW_ALERT_STEP_KEY) != WIZ_PRICE_MIN:
            await q.answer()
            return
        await wiz_price_preset_cb(update, context)
        return

    if data.startswith("nbd_"):
        if context.user_data.get(NEW_ALERT_STEP_KEY) != WIZ_NEIGHBORHOODS:
            await q.answer()
            return
        await wiz_neighborhoods_cb(update, context)
        return

    if data.startswith("wiz_confirm_"):
        if context.user_data.get(NEW_ALERT_STEP_KEY) != WIZ_CONFIRM:
            await q.answer()
            return
        await wiz_confirm_cb(update, context)
        return

    if re.match(r"^alert_toggle_\d+$", data):
        await _alert_toggle_cb(update, context)
        return
    if re.match(r"^alert_delete_\d+$", data):
        await _alert_delete_cb(update, context)
        return
    if re.match(r"^watch_remove_\d+$", data):
        await _watch_remove_cb(update, context)
        return
    if re.match(r"^crs_\d+(?:_notif)?_(prev|next|pgp|pgn)$", data):
        await _carousel_cb(update, context)
        return

    logger.warning("callback desconhecido: %s", data)
    await q.answer()
