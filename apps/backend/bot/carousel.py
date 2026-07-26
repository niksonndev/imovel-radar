"""
Carrossel de anuncios: camada de apresentacao pura.

Recebe uma ``list[HydratedListing]`` e renderiza no Telegram como uma sequência
paginada de mensagens com foto (quando disponível) e teclado inline.

Este módulo **não** acessa o banco de dados; a responsabilidade de buscar
e normalizar os anúncios é de quem chama ``send_carousel``.

Estado do carrossel fica em um dict passado pelo caller (``state_store``):
tipicamente ``app.bot_data`` para que o handler de navegação consiga ler o
mesmo estado mesmo quando o carrossel é disparado fora de um update de
usuário (ex.: job de notificação do scheduler).

Funções/objetos públicos:
- ``send_carousel`` — envia a primeira página e grava o estado em ``state_store``.
- ``carousel_nav_cb`` — handler dos botões ``crs_<id>_<action>``; lê estado
  de ``context.application.bot_data``.
- ``register_handlers`` — registra ``carousel_nav_cb`` no ``Application``.
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

from bot.hydrator import HydratedListing, hydrate_listing
from database import get_connection, get_listings_by_ids
from models import CustomContext, Properties
from utils.pricing import format_brl

logger = logging.getLogger(__name__)

PAGE_SIZE = 10
MAX_TITLE_LEN = 80
CAROUSEL_CALLBACK_PREFIX = "crs_"

_NAV_ACTIONS = frozenset({"next", "prev"})


# ────────────────────── helpers de paginação/legenda ──────────────────────


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
        props.update(item)

    title = _truncate(listing.title, MAX_TITLE_LEN)
    price = format_brl(listing.priceValue)
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
    # Só oferece o link quando o anúncio realmente tem URL válida;
    # evita mandar o usuário para a home da OLX por engano.
    if isinstance(url, str) and url.startswith("http"):
        rows.append([InlineKeyboardButton("🔗 Ver anúncio", url=url)])
    return InlineKeyboardMarkup(rows)


def _parse_nav_callback(data: str) -> tuple[str, str] | None:
    """Extrai (carousel_id, action) de ``crs_<id>_<action>``."""
    if not data.startswith(CAROUSEL_CALLBACK_PREFIX):
        return None
    rest = data[len(CAROUSEL_CALLBACK_PREFIX) :]
    carousel_id, sep, action = rest.rpartition("_")
    if not sep or not carousel_id or action not in _NAV_ACTIONS:
        return None
    return carousel_id, action


def _state_key(carousel_id: str) -> str:
    return f"carousel_{carousel_id}"


# ────────────────────── enviar carrossel ──────────────────────


async def send_carousel(
    bot: Bot,
    chat_id: int,
    listings: list[HydratedListing],
    carousel_id: str,
    state_store: MutableMapping[str, object],
) -> None:
    """Envia a primeira página do carrossel e grava o estado em *state_store*.

    *state_store* deve ser o mesmo dict lido pelo handler de navegação —
    normalmente ``app.bot_data``. O ``carousel_id`` deve ser **globalmente
    único** (ex.: ``str(alert_id)`` para o seed, ``f"{alert_id}n"`` para
    notificação recorrente), já que a chave ``carousel_<id>`` é compartilhada.

    Apenas os IDs dos listings são persistidos — a navegação re-busca os
    dados do banco a cada clique, garantindo que anúncios removidos (active=0)
    somem do carrossel automaticamente.
    """

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
        "listing_ids": [item.listId for item in listings],
        "index": 0,
    }


async def carousel_nav_cb(update: Update, context: CustomContext) -> None:
    """Handler para os botões Anterior/Próximo do carrossel."""
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

    conn = get_connection()
    try:
        raw_listings = get_listings_by_ids(conn, state["listing_ids"])
    finally:
        conn.close()

    listings = [hydrate_listing(listing) for listing in raw_listings]
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
    state["listing_ids"] = [item.listId for item in listings]
    bot_data[_state_key(carousel_id)] = state

    await query.answer()

    caption = _carousel_caption(listing, new_index, total)
    keyboard = _carousel_keyboard(carousel_id, new_index, total, listing.url)
    await query.edit_message_media(
        media=InputMediaPhoto(media=listing.images[0], caption=caption),
        reply_markup=keyboard,
    )


def register_handlers(app: Application) -> None:
    """Registra o ``CallbackQueryHandler`` de navegacao do carrossel."""
    app.add_handler(
        CallbackQueryHandler(
            carousel_nav_cb,
            pattern=r"^crs_.+_(?:next|prev|pgn|pgp)$",
        )
    )
