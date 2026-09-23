"""
Carrossel de anuncios: camada de apresentacao pura.

Recebe uma ``list[Listing]`` e renderiza no Telegram como uma sequência
navegável de mensagens com foto e teclado inline.

Assumimos que ``listing.images[0]`` está sempre disponível.
Navegação é *stateless* no índice (callback ``crs_{id}_{index}``) — não grava
``bot_data`` a cada clique. Só atualiza o store quando aprende um ``file_id``
novo (Telegram CDN) ou ao criar/expirar o carrossel.
"""

from __future__ import annotations

import logging
import time
from collections.abc import MutableMapping
from typing import Any, Literal, TypedDict

from shared_models.tables import Listing
from shared_models.utils import format_brl
from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
    Update,
)
from telegram.ext import Application, CallbackQueryHandler

import config
from models import CustomContext

logger = logging.getLogger(__name__)

MAX_TITLE_LEN = 80
CAROUSEL_CALLBACK_PREFIX = "crs_"
CarouselMode = Literal["matches", "watchlist"]
# Espelha o TTL de drafts (ADR 0006); carrosséis velhos são podados no store.
CAROUSEL_TTL_SECONDS = int(config.DYNAMODB_TTL_HOURS * 3600)


class CarouselCard(TypedDict, total=False):
    listing_id: int
    watch_id: int
    title: str
    price_value: int | None
    neighbourhood: str
    url: str | None
    image_url: str
    file_id: str | None
    rooms: Any
    size: Any
    real_estate_type: str
    listing_active: bool


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _listing_to_card(
    listing: Listing,
    *,
    watch_id: int | None = None,
) -> CarouselCard:
    props = listing.properties if isinstance(listing.properties, dict) else {}
    images = listing.images or []
    card: CarouselCard = {
        "listing_id": listing.listing_id,
        "title": listing.title or "",
        "price_value": listing.price_value,
        "neighbourhood": listing.neighbourhood or "",
        "url": listing.url,
        "image_url": images[0],
        "file_id": None,
        "rooms": props.get("rooms"),
        "size": props.get("size"),
        "real_estate_type": str(props.get("real_estate_type") or "—"),
        "listing_active": bool(listing.active),
    }
    if watch_id is not None:
        card["watch_id"] = watch_id
    return card


def _card_caption(
    card: CarouselCard,
    index: int,
    total: int,
    *,
    mode: CarouselMode = "matches",
) -> str:
    title = _truncate(card.get("title") or "", MAX_TITLE_LEN)
    price = format_brl(card.get("price_value"))
    bedrooms = card.get("rooms")
    bedrooms_label = f"{bedrooms} quarto(s)" if bedrooms is not None else "—"
    area = card.get("size")
    area_label = f"{area:g}m²" if area else "—"
    neighbourhood = card.get("neighbourhood") or "—"
    rental_or_sale = card.get("real_estate_type") or "—"
    counter = f"{index + 1} de {total}"

    lines = [
        f"🏠 {title}",
        f"💰 {price} | 🛏 {bedrooms_label} | 📐 {area_label}",
        f"📍 {neighbourhood} · {rental_or_sale}",
    ]
    if mode == "watchlist":
        status = "✅ No ar" if card.get("listing_active", True) else "❌ Fora do ar"
        lines.append(status)
    lines.extend(["", counter])
    return "\n".join(lines)


def _carousel_keyboard(
    carousel_id: str,
    index: int,
    total: int,
    url: str | None,
    listing_id: int | None = None,
    *,
    mode: CarouselMode = "matches",
    watch_id: int | None = None,
) -> InlineKeyboardMarkup:
    nav_row: list[InlineKeyboardButton] = []
    if index > 0:
        nav_row.append(
            InlineKeyboardButton(
                "◀ Anterior",
                callback_data=f"crs_{carousel_id}_{index - 1}",
            )
        )
    if index < total - 1:
        nav_row.append(
            InlineKeyboardButton(
                "Próximo ▶",
                callback_data=f"crs_{carousel_id}_{index + 1}",
            )
        )
    rows: list[list[InlineKeyboardButton]] = []
    if nav_row:
        rows.append(nav_row)
    action_row: list[InlineKeyboardButton] = []
    if isinstance(url, str) and url.startswith("http"):
        action_row.append(InlineKeyboardButton("🔗 Ver anúncio", url=url))
    if mode == "watchlist":
        if watch_id is not None:
            action_row.append(
                InlineKeyboardButton(
                    "🗑️ Parar de acompanhar",
                    callback_data=f"wl_rm_{watch_id}",
                )
            )
    elif listing_id is not None:
        action_row.append(
            InlineKeyboardButton("👀 Acompanhar", callback_data=f"wch_{listing_id}")
        )
    if action_row:
        rows.append(action_row)
    rows.append([InlineKeyboardButton("🏠 Menu principal", callback_data="menu_home")])
    return InlineKeyboardMarkup(rows)


def _parse_nav_callback(data: str) -> tuple[str, int] | None:
    """``crs_{carousel_id}_{index}`` — índice absoluto (estilo cinema-bot)."""
    if not data.startswith(CAROUSEL_CALLBACK_PREFIX):
        return None
    rest = data[len(CAROUSEL_CALLBACK_PREFIX) :]
    carousel_id, sep, index_s = rest.rpartition("_")
    if not sep or not carousel_id:
        return None
    try:
        index = int(index_s)
    except ValueError:
        return None
    if index < 0:
        return None
    return carousel_id, index


def _state_key(carousel_id: str) -> str:
    return f"carousel_{carousel_id}"


def _photo_file_id(message: Message | bool | None) -> str | None:
    if message is None or isinstance(message, bool):
        return None
    photo = getattr(message, "photo", None)
    if not photo:
        return None
    last = photo[-1]
    file_id = getattr(last, "file_id", None)
    return file_id if isinstance(file_id, str) and file_id else None


def _media_source(card: CarouselCard) -> str:
    file_id = card.get("file_id")
    if isinstance(file_id, str) and file_id:
        return file_id
    image_url = card.get("image_url")
    if isinstance(image_url, str) and image_url:
        return image_url
    raise ValueError("card sem image_url/file_id")


def _is_expired(state: dict[str, Any], *, now: float | None = None) -> bool:
    ts = state.get("created_at")
    if not isinstance(ts, (int, float)):
        return True
    return (now if now is not None else time.time()) - float(ts) > CAROUSEL_TTL_SECONDS


def prune_expired_carousels(
    state_store: MutableMapping[str, object],
    *,
    now: float | None = None,
) -> int:
    """Remove carrosséis expirados do store. Retorna quantos foram removidos."""
    removed = 0
    for key in list(state_store.keys()):
        if not isinstance(key, str) or not key.startswith("carousel_"):
            continue
        value = state_store.get(key)
        if not isinstance(value, dict) or _is_expired(value, now=now):
            state_store.pop(key, None)
            removed += 1
    return removed


async def send_carousel(
    bot: Bot,
    chat_id: int,
    listings: list[Listing],
    carousel_id: str,
    state_store: MutableMapping[str, object],
    *,
    mode: CarouselMode = "matches",
    watch_ids: list[int] | None = None,
) -> None:
    prune_expired_carousels(state_store)

    if mode == "watchlist":
        if watch_ids is None or len(watch_ids) != len(listings):
            raise ValueError("watchlist carousel requires watch_ids aligned with listings")
        cards = [
            _listing_to_card(item, watch_id=watch_id)
            for item, watch_id in zip(listings, watch_ids, strict=True)
        ]
    else:
        cards = [_listing_to_card(item) for item in listings]

    total = len(cards)
    if total == 0:
        raise ValueError("carousel requires at least one listing")

    card = cards[0]
    caption = _card_caption(card, 0, total, mode=mode)
    watch_id = card.get("watch_id")
    keyboard = _carousel_keyboard(
        carousel_id,
        0,
        total,
        card.get("url"),
        card.get("listing_id"),
        mode=mode,
        watch_id=watch_id if isinstance(watch_id, int) else None,
    )

    message = await bot.send_photo(
        chat_id=chat_id,
        photo=_media_source(card),
        caption=caption,
        reply_markup=keyboard,
    )
    file_id = _photo_file_id(message)
    if file_id:
        cards[0]["file_id"] = file_id

    state_store[_state_key(carousel_id)] = {
        "chat_id": chat_id,
        "cards": cards,
        "mode": mode,
        "created_at": time.time(),
    }


async def carousel_nav_cb(update: Update, context: CustomContext) -> None:
    query = update.callback_query
    if query is None:
        return

    parsed = _parse_nav_callback(query.data or "")
    if parsed is None:
        await query.answer()
        return

    carousel_id, new_index = parsed
    bot_data = context.application.bot_data
    key = _state_key(carousel_id)
    state = bot_data.get(key) if bot_data is not None else None

    expired_hint = (
        "Carrossel expirado. Abra Anúncios acompanhados de novo."
        if isinstance(state, dict) and state.get("mode") == "watchlist"
        else "Carrossel expirado. Crie um novo alerta para ver os imoveis."
    )

    if not isinstance(state, dict) or _is_expired(state):
        if isinstance(state, dict) and bot_data is not None:
            bot_data.pop(key, None)
        await query.answer(expired_hint, show_alert=False)
        return

    cards_raw = state.get("cards")
    if not isinstance(cards_raw, list) or not cards_raw:
        # Legacy payload (listings completos) ou vazio — trata como expirado.
        if bot_data is not None:
            bot_data.pop(key, None)
        await query.answer(expired_hint, show_alert=False)
        return

    total = len(cards_raw)
    if new_index < 0 or new_index >= total:
        await query.answer()
        return

    card = cards_raw[new_index]
    if not isinstance(card, dict):
        await query.answer()
        return

    # Spinner some antes da troca de mídia (potealmente lenta na 1ª visita).
    await query.answer()

    mode_raw = state.get("mode")
    mode: CarouselMode = "watchlist" if mode_raw == "watchlist" else "matches"
    caption = _card_caption(card, new_index, total, mode=mode)  # type: ignore[arg-type]
    listing_id = card.get("listing_id")
    watch_id = card.get("watch_id")
    keyboard = _carousel_keyboard(
        carousel_id,
        new_index,
        total,
        card.get("url"),
        listing_id if isinstance(listing_id, int) else None,
        mode=mode,
        watch_id=watch_id if isinstance(watch_id, int) else None,
    )

    try:
        media = _media_source(card)  # type: ignore[arg-type]
    except ValueError:
        logger.warning("Card %s do carrossel %s sem mídia", new_index, carousel_id)
        return

    message = await query.edit_message_media(
        media=InputMediaPhoto(media=media, caption=caption),
        reply_markup=keyboard,
    )

    # Só grava bot_data se aprendemos um file_id novo (CDN do Telegram).
    learned = _photo_file_id(message)
    if learned and not card.get("file_id"):
        card["file_id"] = learned
        cards_raw[new_index] = card
        state["cards"] = cards_raw
        bot_data[key] = state


def register_handlers(app: Application) -> None:
    app.add_handler(
        CallbackQueryHandler(
            carousel_nav_cb,
            pattern=r"^crs_.+_\d+$",
        )
    )
