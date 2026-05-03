"""
Carrossel de anúncios: camada de apresentação pura.

Recebe anúncios já normalizados por ``bot.alert_matching`` (ou outro
orquestrador) e renderiza no Telegram como uma sequência paginada com foto,
legenda e teclado inline.

Este módulo não acessa o banco de dados. O estado do carrossel fica no
``state_store`` passado pelo caller, normalmente ``app.bot_data``, para que a
navegação funcione também em carrosséis disparados fora de um update de
usuário, como notificações do scheduler.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any, TypedDict, cast
from urllib.parse import urlparse

from telegram import (
    Bot,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Update,
)
from telegram.error import BadRequest, TelegramError
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from utils.pricing import format_brl, money_to_int

logger = logging.getLogger(__name__)

PAGE_SIZE = 10
MAX_TITLE_LEN = 80
CAROUSEL_CALLBACK_PREFIX = "crs_"

_MAX_CALLBACK_DATA_BYTES = 64
_NAV_ACTIONS = frozenset({"next", "prev", "pgn", "pgp"})
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")

Ad = Mapping[str, Any]


class CarouselState(TypedDict):
    chat_id: int
    listings: list[Ad]
    index: int
    is_photo: bool


class AdView(TypedDict):
    title: str
    price: str
    bedrooms: int | None
    area_m2: float | None
    neighbourhood: str
    transaction_label: str
    photo_url: str | None
    listing_url: str | None


class CarouselPage(TypedDict):
    caption: str
    keyboard: InlineKeyboardMarkup
    photo_url: str | None


def _state_key(carousel_id: str) -> str:
    return f"carousel_{carousel_id}"


def _clamp_index(index: int, total: int) -> int:
    if total <= 0:
        return 0
    return min(max(index, 0), total - 1)


def _page_info(index: int, total: int) -> tuple[int, int, int, int]:
    """Retorna (page 0-based, total_pages, idx_in_page, items_on_page)."""
    safe_total = max(total, 0)
    safe_index = _clamp_index(index, safe_total)
    total_pages = max(1, (safe_total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = safe_index // PAGE_SIZE
    page_start = page * PAGE_SIZE
    items_on_page = max(0, min(PAGE_SIZE, safe_total - page_start))
    idx_in_page = safe_index - page_start
    return page, total_pages, idx_in_page, items_on_page


def _callback_data(carousel_id: str, action: str) -> str:
    data = f"{CAROUSEL_CALLBACK_PREFIX}{carousel_id}_{action}"
    if len(data.encode("utf-8")) > _MAX_CALLBACK_DATA_BYTES:
        raise ValueError(
            f"carousel_id {carousel_id!r} gera callback_data acima de "
            f"{_MAX_CALLBACK_DATA_BYTES} bytes"
        )
    return data


def _validate_carousel_id(carousel_id: str) -> str:
    normalized = str(carousel_id).strip()
    if not normalized:
        raise ValueError("carousel_id não pode ser vazio")
    for action in _NAV_ACTIONS:
        _callback_data(normalized, action)
    return normalized


def _valid_http_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    candidate = value.strip()
    parsed = urlparse(candidate)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return candidate
    return None


def _normalize_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        match = _NUMBER_RE.search(value)
        if match is not None:
            return int(float(match.group(0).replace(",", ".")))
    return None


def _normalize_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = _NUMBER_RE.search(value)
        if match is None:
            return None
        try:
            return float(match.group(0).replace(",", "."))
        except ValueError:
            return None
    return None


def _format_price(value: object) -> str:
    if isinstance(value, bool) or value is None:
        return format_brl(None)
    if isinstance(value, int):
        return format_brl(value)
    if isinstance(value, float) and value.is_integer():
        return format_brl(int(value))
    if isinstance(value, str):
        stripped = value.strip()
        if re.fullmatch(r"\d+(?:[.,]0+)?", stripped):
            return format_brl(int(float(stripped.replace(",", "."))))
        return format_brl(money_to_int(stripped))
    return format_brl(None)


def _display_text(value: object, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _transaction_label(ad: Ad) -> str:
    """Deriva o rótulo (Aluguel/Venda) a partir de ``category`` do anúncio."""
    category = str(ad.get("category") or "").lower()
    if "sale" in category or "venda" in category:
        return "Venda"
    return "Aluguel"


def _properties_to_dict(props: object) -> dict[str, object]:
    """Normaliza properties do anúncio para um dict simples {campo: valor}."""
    if props is None:
        return {}

    data = props
    if isinstance(props, str):
        try:
            data = json.loads(props)
        except json.JSONDecodeError:
            logger.debug("properties inválido no anúncio: %r", props)
            return {}

    out: dict[str, object] = {}
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, Mapping):
                continue
            for key, value in item.items():
                if isinstance(key, str):
                    out[key.strip().lower()] = value
    elif isinstance(data, Mapping):
        for key, value in data.items():
            if isinstance(key, str):
                out[key.strip().lower()] = value
    return out


def rooms_from_properties(props: object) -> int | None:
    return _normalize_int(_properties_to_dict(props).get("rooms"))


def area_m2_from_properties(props: object) -> float | None:
    return _normalize_float(_properties_to_dict(props).get("size"))


def _carousel_photo_url(ad: Ad) -> str | None:
    images = ad.get("images")
    if not isinstance(images, list) or not images:
        return None

    first_image = images[0]
    if photo_url := _valid_http_url(first_image):
        return photo_url

    if isinstance(first_image, Mapping):
        return _valid_http_url(
            first_image.get("originalWebp") or first_image.get("original")
        )
    return None


def _ad_view(ad: Ad) -> AdView:
    properties = _properties_to_dict(ad.get("properties"))

    bedrooms = _normalize_int(ad.get("bedrooms"))
    if bedrooms is None:
        bedrooms = _normalize_int(properties.get("rooms"))

    area = _normalize_float(ad.get("area_m2"))
    if area is None:
        area = _normalize_float(properties.get("size"))

    return {
        "title": _truncate(_display_text(ad.get("title"), "Imóvel"), MAX_TITLE_LEN),
        "price": _format_price(ad.get("priceValue")),
        "bedrooms": bedrooms,
        "area_m2": area,
        "neighbourhood": _display_text(
            ad.get("neighbourhood") or ad.get("neighborhood"),
            "—",
        ),
        "transaction_label": _transaction_label(ad),
        "photo_url": _carousel_photo_url(ad),
        "listing_url": _valid_http_url(ad.get("url")),
    }


def _rooms_label(count: int | None) -> str:
    if count is None:
        return "—"
    suffix = "quarto" if count == 1 else "quartos"
    return f"{count} {suffix}"


def _carousel_caption(view: AdView, index: int, total: int) -> str:
    area = view["area_m2"]
    area_s = f"{area:g}m²" if area is not None and area > 0 else "—"
    page, total_pages, idx_in_page, items_on_page = _page_info(index, total)
    counter = (
        f"{idx_in_page + 1} de {items_on_page} — Página {page + 1} de {total_pages}"
    )

    return (
        f"🏠 {view['title']}\n"
        f"💰 {view['price']} | 🛏 {_rooms_label(view['bedrooms'])} | 📐 {area_s}\n"
        f"📍 {view['neighbourhood']} · {view['transaction_label']}\n\n"
        f"{counter}"
    )


def _carousel_keyboard(
    carousel_id: str,
    index: int,
    total: int,
    url: str | None,
) -> InlineKeyboardMarkup:
    page, total_pages, idx_in_page, items_on_page = _page_info(index, total)

    nav_row: list[InlineKeyboardButton] = []
    if idx_in_page > 0:
        nav_row.append(
            InlineKeyboardButton(
                "◀ Anterior",
                callback_data=_callback_data(carousel_id, "prev"),
            )
        )
    if idx_in_page < items_on_page - 1:
        nav_row.append(
            InlineKeyboardButton(
                "Próximo ▶",
                callback_data=_callback_data(carousel_id, "next"),
            )
        )

    page_row: list[InlineKeyboardButton] = []
    if page > 0:
        page_row.append(
            InlineKeyboardButton(
                "◀ Página anterior",
                callback_data=_callback_data(carousel_id, "pgp"),
            )
        )
    if page < total_pages - 1:
        page_row.append(
            InlineKeyboardButton(
                "⏭ Próxima página",
                callback_data=_callback_data(carousel_id, "pgn"),
            )
        )

    rows: list[list[InlineKeyboardButton]] = []
    if nav_row:
        rows.append(nav_row)
    if page_row:
        rows.append(page_row)
    if url is not None:
        rows.append([InlineKeyboardButton("🔗 Ver anúncio", url=url)])
    return InlineKeyboardMarkup(rows)


def _carousel_page(
    ad: Ad,
    *,
    carousel_id: str,
    index: int,
    total: int,
) -> CarouselPage:
    view = _ad_view(ad)
    return {
        "caption": _carousel_caption(view, index, total),
        "keyboard": _carousel_keyboard(
            carousel_id,
            index,
            total,
            view["listing_url"],
        ),
        "photo_url": view["photo_url"],
    }


async def _send_carousel_page(
    bot: Bot,
    *,
    chat_id: int,
    page: CarouselPage,
    carousel_id: str,
) -> bool:
    """Envia uma página. Retorna True quando a mensagem enviada é foto."""
    if page["photo_url"] is not None:
        try:
            await bot.send_photo(
                chat_id=chat_id,
                photo=page["photo_url"],
                caption=page["caption"],
                reply_markup=page["keyboard"],
            )
            return True
        except TelegramError as exc:
            logger.warning(
                "Foto do carrossel %s recusada pelo Telegram (%s); enviando texto.",
                carousel_id,
                exc,
            )

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=page["caption"],
            reply_markup=page["keyboard"],
        )
    except TelegramError:
        logger.exception(
            "Falha ao enviar carrossel %s para chat %s",
            carousel_id,
            chat_id,
        )
        raise
    return False


def _coerce_state(state: object) -> CarouselState | None:
    if not isinstance(state, dict):
        return None

    listings = state.get("listings")
    if not isinstance(listings, list) or not listings:
        return None

    chat_id = _normalize_int(state.get("chat_id"))
    index = _normalize_int(state.get("index"))
    if chat_id is None or index is None:
        return None

    state["chat_id"] = chat_id
    state["index"] = _clamp_index(index, len(listings))
    state["is_photo"] = bool(state.get("is_photo"))
    return cast(CarouselState, state)


async def send_carousel(
    bot: Bot,
    chat_id: int,
    ads: Sequence[Ad],
    carousel_id: str,
    state_store: MutableMapping[str, object],
) -> None:
    """Envia a primeira página do carrossel e grava o estado em *state_store*.

    ``carousel_id`` deve ser globalmente único e curto o bastante para caber no
    limite de ``callback_data`` do Telegram.
    """
    listings = cast(list[Ad], ads) if isinstance(ads, list) else list(ads)
    if not listings:
        raw_carousel_id = str(carousel_id).strip()
        if raw_carousel_id:
            state_store.pop(_state_key(raw_carousel_id), None)
        logger.warning(
            "Carrossel %s não enviado: lista de anúncios vazia.",
            carousel_id,
        )
        return

    carousel_id = _validate_carousel_id(carousel_id)
    page = _carousel_page(
        listings[0],
        carousel_id=carousel_id,
        index=0,
        total=len(listings),
    )
    is_photo = await _send_carousel_page(
        bot,
        chat_id=chat_id,
        page=page,
        carousel_id=carousel_id,
    )

    state_store[_state_key(carousel_id)] = {
        "chat_id": chat_id,
        "listings": listings,
        "index": 0,
        "is_photo": is_photo,
    }


def _parse_nav_callback(data: str) -> tuple[str, str] | None:
    """Extrai (carousel_id, action) de ``crs_<id>_<action>``."""
    if not data.startswith(CAROUSEL_CALLBACK_PREFIX):
        return None
    rest = data[len(CAROUSEL_CALLBACK_PREFIX) :]
    carousel_id, sep, action = rest.rpartition("_")
    if not sep or not carousel_id or action not in _NAV_ACTIONS:
        return None
    return carousel_id, action


def _next_index(index: int, action: str, total: int) -> int:
    if total <= 0:
        return 0

    safe_index = _clamp_index(index, total)
    page = safe_index // PAGE_SIZE
    if action == "next":
        return min(safe_index + 1, total - 1)
    if action == "prev":
        return max(safe_index - 1, 0)
    if action == "pgn":
        return min((page + 1) * PAGE_SIZE, total - 1)
    if action == "pgp":
        return max((page - 1) * PAGE_SIZE, 0)
    return safe_index


async def _replace_message_with_page(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    carousel_id: str,
    page: CarouselPage,
    state: CarouselState,
) -> None:
    message = query.message
    if message is None:
        logger.warning("Mensagem ausente ao atualizar carrossel %s.", carousel_id)
        return

    is_photo = await _send_carousel_page(
        context.bot,
        chat_id=message.chat_id,
        page=page,
        carousel_id=carousel_id,
    )
    state["is_photo"] = is_photo

    try:
        await message.delete()
    except TelegramError:
        logger.debug(
            "Não foi possível apagar mensagem antiga do carrossel %s",
            carousel_id,
        )


async def _render_carousel_update(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    carousel_id: str,
    state: CarouselState,
) -> None:
    ads = state["listings"]
    total = len(ads)
    if total == 0:
        logger.warning("Carrossel %s ficou sem anúncios no estado.", carousel_id)
        return

    index = _clamp_index(state["index"], total)
    state["index"] = index
    page = _carousel_page(
        ads[index],
        carousel_id=carousel_id,
        index=index,
        total=total,
    )
    was_photo = state["is_photo"]
    has_photo = page["photo_url"] is not None

    try:
        if was_photo and has_photo:
            await query.edit_message_media(
                media=InputMediaPhoto(
                    media=page["photo_url"],
                    caption=page["caption"],
                ),
                reply_markup=page["keyboard"],
            )
            return

        if not was_photo and not has_photo:
            await query.edit_message_text(
                text=page["caption"],
                reply_markup=page["keyboard"],
            )
            return

        await _replace_message_with_page(
            query,
            context,
            carousel_id=carousel_id,
            page=page,
            state=state,
        )
    except BadRequest as exc:
        if "message is not modified" in str(exc).lower():
            logger.debug("Carrossel %s sem alteração: %s", carousel_id, exc)
            return
        logger.exception("Telegram recusou atualização do carrossel %s", carousel_id)
    except TelegramError:
        logger.exception("Erro ao renderizar carrossel %s", carousel_id)


async def carousel_nav_cb(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handler para os botões Anterior/Próximo/Páginas do carrossel."""
    query = update.callback_query
    if query is None:
        return

    parsed = _parse_nav_callback(query.data or "")
    if parsed is None:
        await query.answer()
        return

    carousel_id, action = parsed
    bot_data = context.application.bot_data
    key = _state_key(carousel_id)
    state = _coerce_state(bot_data.get(key) if bot_data is not None else None)
    if state is None:
        if bot_data is not None:
            bot_data.pop(key, None)
        logger.warning("Carrossel %s expirado ou com estado inválido.", carousel_id)
        await query.answer(
            "Carrossel expirado. Crie um novo alerta para ver os imóveis.",
            show_alert=False,
        )
        return

    new_index = _next_index(state["index"], action, len(state["listings"]))
    if new_index == state["index"]:
        await query.answer()
        return

    state["index"] = new_index
    await query.answer()
    await _render_carousel_update(query, context, carousel_id, state)


def register_handlers(app: Application) -> None:
    """Registra o ``CallbackQueryHandler`` de navegação do carrossel."""
    app.add_handler(
        CallbackQueryHandler(
            carousel_nav_cb,
            pattern=r"^crs_.+_(?:next|prev|pgn|pgp)$",
        )
    )
