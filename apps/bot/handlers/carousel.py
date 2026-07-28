"""
Carrossel de anuncios: camada de apresentacao pura.

Recebe uma ``list[HydratedListing]`` e renderiza no Telegram como uma sequência
paginada de mensagens com foto (quando disponível) e teclado inline.

Este módulo não acessa o banco de dados — usa a API do scraper via ``bot.api_client``.
"""

from __future__ import annotations

import logging
from collections.abc import MutableMapping

from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Update,
)
from telegram.ext import Application, CallbackQueryHandler

from handlers.api_client import ScraperAPI
from handlers.hydrator import hydrate_listing
from models import CustomContext
from shared_models import HydratedListing, Properties
from shared_models.utils import format_brl

logger = logging.getLogger(__name__)

PAGE_SIZE = 10
MAX_TITLE_LEN = 80
CAROUSEL_CALLBACK_PREFIX = "crs_"

_NAV_ACTIONS = frozenset({"next", "prev"})


def _next_index(index: int, action: str, total: int) -> int:
    if action == "next":
        return min(index + 1, total - 1)
    if action == "prev":
        return max(index - 1, 0)
    return index


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _carousel_caption(listing: HydratedListing, index: int, total: int) -> str:
    props: Properties = {}
    for item in listing.properties:
        props.update(item.model_dump())

    title = _truncate(listing.title, MAX_TITLE_LEN)
    price = format_brl(listing.price_value)
    bedrooms = props.get("rooms")
    bedrooms_label = f"{bedrooms} quarto(s)" if bedrooms is not None else "—"
    area = props.get("size")
    area_label = f"{area:g}m²" if area else "—"
    neighbourhood = listing.neighbourhood or "—"
    rental_or_sale = props.get("real_estate_type", "—")

    counter = f"{index + 1} de {total}"

    return (
        f"🏠 {title}\n"
        f"💰 {price} | 🛏 {bedrooms_label} | 📐 {area_label}\n"
        f"📍 {neighbourhood} · {rental_or_sale}\n\n"
        f"{counter}"
    )


def _carousel_keyboard(
    carousel_id: str,
    index: int,
    total: int,
    url: str | None,
) -> InlineKeyboardMarkup:
    nav_row: list[InlineKeyboardButton] = []
    if index > 0:
        nav_row.append(InlineKeyboardButton("◀ Anterior", callback_data=f"crs_{carousel_id}_prev"))
    if index < total - 1:
        nav_row.append(InlineKeyboardButton("Próximo ▶", callback_data=f"crs_{carousel_id}_next"))
    rows: list[list[InlineKeyboardButton]] = []
    if nav_row:
        rows.append(nav_row)
    if isinstance(url, str) and url.startswith("http"):
        rows.append([InlineKeyboardButton("🔗 Ver anúncio", url=url)])
    return InlineKeyboardMarkup(rows)


def _parse_nav_callback(data: str) -> tuple[str, str] | None:
    if not data.startswith(CAROUSEL_CALLBACK_PREFIX):
        return None
    rest = data[len(CAROUSEL_CALLBACK_PREFIX):]
    carousel_id, sep, action = rest.rpartition("_")
    if not sep or not carousel_id or action not in _NAV_ACTIONS:
        return None
    return carousel_id, action


def _state_key(carousel_id: str) -> str:
    return f"carousel_{carousel_id}"


async def send_carousel(
    bot: Bot,
    chat_id: int,
    listings: list[HydratedListing],
    carousel_id: str,
    state_store: MutableMapping[str, object],
) -> None:
    total = len(listings)
    listing = listings[0]
    caption = _carousel_caption(listing, 0, total)
    keyboard = _carousel_keyboard(carousel_id, 0, total, listing.url)

    await bot.send_photo(
        chat_id=chat_id,
        photo=listing.images[0],
        caption=caption,
        reply_markup=keyboard,
    )

    state_store[_state_key(carousel_id)] = {
        "chat_id": chat_id,
        "listing_ids": [item.list_id for item in listings],
        "index": 0,
    }


async def carousel_nav_cb(update: Update, context: CustomContext) -> None:
    query = update.callback_query
    if query is None:
        return

    parsed = _parse_nav_callback(query.data or "")
    if parsed is None:
        await query.answer()
        return

    carousel_id, action = parsed
    bot_data = context.application.bot_data
    state = bot_data.get(_state_key(carousel_id)) if bot_data is not None else None
    if not isinstance(state, dict) or not state.get("listing_ids"):
        await query.answer(
            "Carrossel expirado. Crie um novo alerta para ver os imoveis.",
            show_alert=False,
        )
        return

    # Fetch listings from the scraper API
    api = ScraperAPI()
    try:
        response = await api.get_listings(ids=state["listing_ids"])
    except Exception:
        await query.answer("Erro ao carregar anúncios. Tente novamente.")
        return
    finally:
        await api.close()

    listings = response.listings
    total = len(listings)
    if total == 0:
        await query.answer("Todos os anúncios deste carrossel foram removidos.")
        return

    current: int = min(int(state.get("index", 0)), total - 1)
    new_index = _next_index(current, action, total)
    if new_index == current:
        await query.answer()
        return

    listing = listings[new_index]
    state["index"] = new_index
    state["listing_ids"] = [item.list_id for item in listings]
    bot_data[_state_key(carousel_id)] = state

    await query.answer()

    caption = _carousel_caption(listing, new_index, total)
    keyboard = _carousel_keyboard(carousel_id, new_index, total, listing.url)
    await query.edit_message_media(
        media=InputMediaPhoto(media=listing.images[0], caption=caption),
        reply_markup=keyboard,
    )


def register_handlers(app: Application) -> None:
    app.add_handler(
        CallbackQueryHandler(
            carousel_nav_cb,
            pattern=r"^crs_.+_(?:next|prev|pgn|pgp)$",
        )
    )