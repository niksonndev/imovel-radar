"""
Handlers de *Anúncios acompanhados*: carrossel, remoção, wizard por URL
e botão do carrossel de matches.
"""

from __future__ import annotations

import logging
import re

from shared_models.tables import Listing, WatchedListingChange
from telegram import CallbackQuery, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from handlers.carousel import send_carousel
from handlers.data import (
    create_watch,
    delete_watch,
    get_listing,
    get_watches_for_user,
    user_is_pro,
    watch_cap_for_user,
)
from handlers.ui import keyboards, menus
from models import CustomContext, WatchlistDraft

logger = logging.getLogger(__name__)

(URL, CONFIRM) = range(2)

WL_PICK_RE = re.compile(r"^wl_p_(\d+)$")
WL_RM_RE = re.compile(r"^wl_rm_(\d+)$")
WCH_RE = re.compile(r"^wch_(\d+)$")

# OLX URLs terminam com ``-{listId}``; também aceita só o id numérico.
_OLX_LISTING_ID_RE = re.compile(
    r"(?:https?://\S*?-)?(\d{8,})(?:[/?#]|$)",
    re.IGNORECASE,
)


def parse_olx_listing_id(text: str) -> int | None:
    """Extrai o ``listId`` de uma URL OLX ou de um id numérico puro."""
    raw = text.strip()
    if not raw:
        return None
    if re.fullmatch(r"\d{8,}", raw):
        return int(raw)
    match = _OLX_LISTING_ID_RE.search(raw)
    if match is None:
        return None
    return int(match.group(1))


def _clear_draft(context: CustomContext) -> None:
    assert context.user_data is not None
    context.user_data.pop("watchlist_draft", None)


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


async def _send_watchlist_view(
    context: CustomContext,
    user_id: int,
    *,
    rows: list[WatchedListingChange],
    cap: int,
) -> None:
    can_add = len(rows) < cap
    header_markup = keyboards.watchlist_header_keyboard(can_add=can_add)

    if not rows:
        await context.bot.send_message(
            chat_id=user_id,
            text=menus.watchlist_empty_message(cap=cap),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=header_markup,
        )
        return

    listings, watch_ids = _rows_with_photos(rows)
    if not listings:
        await context.bot.send_message(
            chat_id=user_id,
            text=menus.watchlist_sem_fotos(count=len(rows), cap=cap),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=header_markup,
        )
        return

    await send_carousel(
        context.application.bot,
        user_id,
        listings,
        _watchlist_carousel_id(user_id),
        context.application.bot_data,
        mode="watchlist",
        watch_ids=watch_ids,
        can_add=can_add,
    )


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
        await query.edit_message_text(
            text=menus.watchlist_erro(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return

    can_add = len(rows) < cap
    header_markup = keyboards.watchlist_header_keyboard(can_add=can_add)

    if not rows:
        await query.edit_message_text(
            text=menus.watchlist_empty_message(cap=cap),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=header_markup,
        )
        return

    listings, watch_ids = _rows_with_photos(rows)
    if not listings:
        try:
            await query.edit_message_text(
                text=menus.watchlist_sem_fotos(count=len(rows), cap=cap),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=header_markup,
            )
        except BadRequest:
            await context.bot.send_message(
                chat_id=user_id,
                text=menus.watchlist_sem_fotos(count=len(rows), cap=cap),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=header_markup,
            )
        return

    # Carrossel só — sem mensagem de cabeçalho acima da foto.
    if query.message is not None:
        try:
            await query.message.delete()
        except Exception:
            logger.debug("Não foi possível apagar a mensagem anterior", exc_info=True)

    await send_carousel(
        context.application.bot,
        user_id,
        listings,
        _watchlist_carousel_id(user_id),
        context.application.bot_data,
        mode="watchlist",
        watch_ids=watch_ids,
        can_add=can_add,
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
        await query.answer()
        menu_text = menus.menu_principal_inline()
        menu_markup = keyboards.main_menu_keyboard()
        if query.message is not None and query.message.photo:
            try:
                await query.message.delete()
            except Exception:
                logger.debug("Não foi possível apagar o card do carrossel", exc_info=True)
            await context.bot.send_message(
                chat_id=user_id,
                text=menu_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=menu_markup,
            )
            return
        try:
            await query.edit_message_text(
                text=menu_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=menu_markup,
            )
        except BadRequest:
            await context.bot.send_message(
                chat_id=user_id,
                text=menu_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=menu_markup,
            )
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
            return
        await query.answer("Removido da lista.")

        if query.message is not None and query.message.photo:
            try:
                await query.message.delete()
            except Exception:
                logger.debug("Não foi possível apagar o card do carrossel", exc_info=True)
            try:
                rows = await get_watches_for_user(user_id)
                cap = await watch_cap_for_user(user_id)
            except Exception:
                logger.exception("Falha ao relistar após remover")
                await context.bot.send_message(
                    chat_id=user_id,
                    text=menus.watchlist_erro(),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboards.main_menu_keyboard(),
                )
                return
            await _send_watchlist_view(context, user_id, rows=rows, cap=cap)
            return

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


# ── Conversation: adicionar por URL ────────────────────────────────────────


async def watchlist_add_entry(update: Update, context: CustomContext) -> int:
    assert context.user_data is not None
    assert update.effective_message is not None

    context.user_data["watchlist_draft"] = WatchlistDraft()

    if update.callback_query is not None:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

    await update.effective_message.reply_text(
        menus.watchlist_url_prompt(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return URL


async def watchlist_url_text(update: Update, context: CustomContext) -> int:
    assert update.effective_message is not None
    assert context.user_data is not None

    listing_id = parse_olx_listing_id(update.effective_message.text or "")
    if listing_id is None:
        await update.effective_message.reply_text(menus.watchlist_url_invalida())
        return URL

    try:
        listing = await get_listing(listing_id)
    except Exception:
        logger.exception("Falha ao buscar listing %s", listing_id)
        await update.effective_message.reply_text(
            "Não consegui consultar o anúncio agora. Tente de novo.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        _clear_draft(context)
        return ConversationHandler.END

    if listing is None:
        await update.effective_message.reply_text(
            menus.watchlist_listing_missing(),
            reply_markup=keyboards.main_menu_keyboard(),
        )
        _clear_draft(context)
        return ConversationHandler.END

    draft = WatchlistDraft(
        listing_id=listing.listing_id,
        title=listing.title or "",
        price_value=listing.price_value,
        neighbourhood=listing.neighbourhood or "",
        url=listing.url or "",
    )
    context.user_data["watchlist_draft"] = draft

    await update.effective_message.reply_text(
        menus.watchlist_confirm_resumo(
            title=draft.get("title") or "",
            price_value=draft.get("price_value"),
            neighbourhood=draft.get("neighbourhood") or "",
        ),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.watchlist_confirm_keyboard(),
    )
    return CONFIRM


async def watchlist_confirm_cb(update: Update, context: CustomContext) -> int:
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    user = update.effective_user
    if user is None:
        return ConversationHandler.END
    assert context.user_data is not None

    await query.answer()
    data = query.data or ""

    if data == "wl_confirm_no":
        _clear_draft(context)
        await query.edit_message_text(
            menus.watchlist_cancelado(),
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return ConversationHandler.END

    draft = context.user_data.get("watchlist_draft")
    listing_id = draft.get("listing_id") if draft else None
    if listing_id is None:
        _clear_draft(context)
        await query.edit_message_text(
            menus.wizard_sessao_expirada_curta(),
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return ConversationHandler.END

    try:
        result = await create_watch(chat_id=user.id, listing_id=listing_id)
    except Exception:
        logger.exception("Falha ao criar acompanhamento")
        await query.edit_message_text(
            "Não consegui salvar agora. Tente de novo.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        _clear_draft(context)
        return ConversationHandler.END

    _clear_draft(context)

    if result.status == "created":
        text = menus.watchlist_created()
        markup = keyboards.main_menu_keyboard()
    elif result.status == "cap_reached":
        try:
            pro = await user_is_pro(user.id)
        except Exception:
            logger.exception("Falha ao checar Pro no cap watchlist URL")
            pro = False
        text = menus.watchlist_cap_reached(is_pro_user=pro)
        markup = (
            keyboards.main_menu_keyboard()
            if pro
            else keyboards.watchlist_cap_upsell_keyboard()
        )
    elif result.status == "duplicate":
        text = menus.watchlist_duplicate()
        markup = keyboards.main_menu_keyboard()
    elif result.status == "listing_missing":
        text = menus.watchlist_listing_missing()
        markup = keyboards.main_menu_keyboard()
    else:
        text = "Não foi possível acompanhar este anúncio."
        markup = keyboards.main_menu_keyboard()

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN if result.status == "cap_reached" else None,
        reply_markup=markup,
    )
    return ConversationHandler.END


async def watchlist_cancel(update: Update, context: CustomContext) -> int:
    assert update.effective_message is not None
    _clear_draft(context)
    await update.effective_message.reply_text(
        menus.watchlist_cancelado(),
        reply_markup=keyboards.main_menu_keyboard(),
    )
    return ConversationHandler.END


async def watchlist_start_fallback(update: Update, context: CustomContext) -> int:
    assert update.effective_message is not None
    _clear_draft(context)
    await update.effective_message.reply_text(
        menus.start_welcome(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.main_menu_keyboard(),
    )
    return ConversationHandler.END


def watchlist_add_conversation() -> ConversationHandler:
    return ConversationHandler(
        name="watchlist_add",
        persistent=True,
        allow_reentry=True,
        entry_points=[
            CallbackQueryHandler(watchlist_add_entry, pattern=r"^wl_add$"),
        ],
        states={
            URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, watchlist_url_text),
            ],
            CONFIRM: [
                CallbackQueryHandler(watchlist_confirm_cb, pattern=r"^wl_confirm_"),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", watchlist_cancel),
            CommandHandler("start", watchlist_start_fallback),
        ],
    )
