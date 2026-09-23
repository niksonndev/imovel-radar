"""
Handlers de *Anúncios acompanhados*: carrossel, remoção
e botão do carrossel de matches.
"""

from __future__ import annotations

import logging
import re

from shared_models.tables import Listing, WatchedListingChange
from telegram import CallbackQuery, Update
from telegram.constants import ParseMode

from handlers.carousel import send_carousel
from handlers.data import (
    create_watch,
    delete_watch,
    get_watches_for_user,
    user_is_pro,
    watch_cap_for_user,
)
from handlers.home import present_message, restore_menu_after_error, show_main_menu
from handlers.ui import keyboards, menus
from models import CustomContext

logger = logging.getLogger(__name__)

WL_PICK_RE = re.compile(r"^wl_p_(\d+)$")
WL_RM_RE = re.compile(r"^wl_rm_(\d+)$")
WCH_RE = re.compile(r"^wch_(\d+)$")


def _watchlist_carousel_id(user_id: int) -> str:
    return f"wl{user_id}"


def _rows_with_photos(
    rows: list[WatchedListingChange],
) -> tuple[list[Listing], list[int]]:
    listings: list[Listing] = []
    watch_ids: list[int] = []
    for row in rows:
        images = row.listing.images or []
        watch_id = row.watch.id
        if not images or watch_id is None:
            continue
        listings.append(row.listing)
        watch_ids.append(watch_id)
    return listings, watch_ids


async def _render_watchlist_list(
    query: CallbackQuery,
    user_id: int,
    context: CustomContext,
) -> None:
    try:
        rows = await get_watches_for_user(user_id)
        cap = await watch_cap_for_user(user_id)
    except Exception:
        logger.exception("Falha ao listar acompanhamentos")
        await present_message(
            query,
            context,
            menus.watchlist_erro(),
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return

    header_markup = keyboards.watchlist_header_keyboard()

    if not rows:
        await present_message(
            query,
            context,
            menus.watchlist_empty_message(cap=cap),
            reply_markup=header_markup,
        )
        return

    listings, watch_ids = _rows_with_photos(rows)
    if not listings:
        await present_message(
            query,
            context,
            menus.watchlist_sem_fotos(count=len(rows), cap=cap),
            reply_markup=header_markup,
        )
        return

    on_photo = query.message is not None and bool(query.message.photo)
    if not on_photo:
        await present_message(
            query,
            context,
            menus.watchlist_carousel_header(count=len(rows), cap=cap),
            reply_markup=header_markup,
        )

    await send_carousel(
        context.application.bot,
        user_id,
        listings,
        _watchlist_carousel_id(user_id),
        context.application.bot_data,
        mode="watchlist",
        watch_ids=watch_ids,
        query=query if on_photo else None,
    )


async def watchlist_menu_callback(update: Update, context: CustomContext) -> None:
    query = update.callback_query
    if query is None:
        return
    user = update.effective_user
    if user is None:
        return
    await query.answer()
    await _render_watchlist_list(query, user.id, context)


async def watchlist_actions_callback(update: Update, context: CustomContext) -> None:
    query = update.callback_query
    if query is None:
        return
    user = update.effective_user
    if user is None:
        return

    data = query.data or ""
    user_id = user.id

    if data == "wl_m":
        await show_main_menu(update, context)
        return

    if data == "wl_b" or WL_PICK_RE.match(data):
        await query.answer()
        await _render_watchlist_list(query, user_id, context)
        return

    m_rm = WL_RM_RE.match(data)
    if m_rm is not None:
        watch_id = int(m_rm.group(1))
        try:
            await delete_watch(watch_id, user_id)
        except Exception:
            logger.exception("Falha ao remover acompanhamento")
            await query.answer("Não foi possível remover.", show_alert=True)
            await restore_menu_after_error(query, context, menus.watchlist_erro())
            return
        await query.answer("Removido da lista.")
        await _render_watchlist_list(query, user_id, context)
        return

    logger.warning("Callback wl_* não reconhecido: %s", data)
    await query.answer()


def _toast_for_create_status(status: str, *, is_pro_user: bool = False) -> str:
    if status == "created":
        return menus.watchlist_created_alert()
    if status == "duplicate":
        return "Você já acompanha este anúncio."
    if status == "cap_reached":
        return menus.watchlist_cap_reached_alert(is_pro_user=is_pro_user)
    if status == "listing_missing":
        return "Anúncio ainda não está no radar."
    return "Não foi possível acompanhar."


async def carousel_watch_callback(update: Update, context: CustomContext) -> None:
    """Botão 👀 Acompanhar no carrossel de matches."""
    query = update.callback_query
    if query is None:
        return
    user = update.effective_user
    if user is None:
        return

    match = WCH_RE.match(query.data or "")
    if match is None:
        await query.answer()
        return

    listing_id = int(match.group(1))
    try:
        result = await create_watch(chat_id=user.id, listing_id=listing_id)
    except Exception:
        logger.exception("Falha ao acompanhar listing %s do carrossel", listing_id)
        await query.answer("Erro ao acompanhar. Tente de novo.", show_alert=True)
        return

    pro = False
    if result.status == "cap_reached":
        try:
            pro = await user_is_pro(user.id)
        except Exception:
            logger.exception("Falha ao checar Pro no cap watchlist")

    await query.answer(
        _toast_for_create_status(result.status, is_pro_user=pro),
        show_alert=True,
    )

    if result.status == "cap_reached" and query.message is not None:
        markup = (
            keyboards.main_menu_keyboard()
            if pro
            else keyboards.watchlist_cap_upsell_keyboard()
        )
        await query.message.reply_text(
            menus.watchlist_cap_reached(is_pro_user=pro),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=markup,
        )
