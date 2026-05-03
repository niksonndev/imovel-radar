"""
Carrossel de anuncios: camada de apresentacao pura.

Recebe uma ``list[dict]`` ja pronta (preparada por ``bot.alert_matching`` ou
por outro orquestrador) e renderiza no Telegram como uma sequencia paginada
de mensagens com foto (quando disponivel) e teclado inline.

Este modulo nao acessa o banco de dados; a responsabilidade de buscar
e normalizar os anuncios e de quem chama ``send_carousel``.

Estado do carrossel fica em um dict passado pelo caller (``state_store``):
tipicamente ``app.bot_data`` para que o handler de navegacao consiga ler o
mesmo estado mesmo quando o carrossel e disparado fora de um update de
usuario (ex.: job de notificacao do scheduler).

Funcoes/objetos publicos:
- ``send_carousel``: envia a primeira pagina e grava o estado em ``state_store``.
- ``carousel_nav_cb``: handler dos botoes ``crs_<id>_<action>``; le estado
  de ``context.application.bot_data``.
- ``register_handlers``: registra ``carousel_nav_cb`` no ``Application``.

Helpers como ``rooms_from_properties`` / ``area_m2_from_properties``
normalizam o JSON de ``properties`` vindo do banco sob demanda.
"""

from __future__ import annotations

import json
import logging
import math
from typing import Any, TypedDict, cast

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

from utils.pricing import format_brl

logger = logging.getLogger(__name__)

PAGE_SIZE = 10
MAX_NOTIF_CAROUSEL = 10
MAX_TITLE_LEN = 80
CAROUSEL_CALLBACK_PREFIX = "crs_"
_NAV_ACTIONS = frozenset({"next", "prev", "pgn", "pgp"})

Ad = dict[str, Any]


class CarouselState(TypedDict):
    chat_id: int
    listings: list[Ad]
    index: int
    page_size: int
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


def _page_info(index: int, total: int) -> tuple[int, int, int, int]:
    """Retorna (page 0-based, total_pages, idx_in_page, items_on_page)."""
    page = index // PAGE_SIZE
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    page_start = page * PAGE_SIZE
    items_on_page = max(0, min(PAGE_SIZE, total - page_start))
    idx_in_page = index - page_start
    return page, total_pages, idx_in_page, items_on_page


def _transaction_label(ad: Ad) -> str:
    """Deriva o rotulo (Aluguel/Venda) a partir de ``category`` do anuncio."""
    category = str(ad.get("category") or "").lower()
    if "sale" in category or "venda" in category:
        return "Venda"
    return "Aluguel"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _valid_http_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if candidate.startswith(("http://", "https://")):
        return candidate
    return None


def _normalize_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
    return None


def _normalize_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip().replace(",", ".")
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _ad_view(ad: Ad) -> AdView:
    properties = ad.get("properties")
    bedrooms = _normalize_int(ad.get("bedrooms"))
    if bedrooms is None:
        bedrooms = rooms_from_properties(properties)

    area = _normalize_float(ad.get("area_m2"))
    if area is None:
        area = area_m2_from_properties(properties)

    neighbourhood = ad.get("neighbourhood") or ad.get("neighborhood") or "-"
    if not isinstance(neighbourhood, str) or not neighbourhood.strip():
        neighbourhood = "-"

    return {
        "title": _truncate(str(ad.get("title") or "Imovel"), MAX_TITLE_LEN),
        "price": format_brl(ad.get("priceValue")),
        "bedrooms": bedrooms,
        "area_m2": area,
        "neighbourhood": neighbourhood.strip(),
        "transaction_label": _transaction_label(ad),
        "photo_url": _carousel_photo_url(ad),
        "listing_url": _valid_http_url(ad.get("url")),
    }


def _carousel_caption(view: AdView, index: int, total: int) -> str:
    bed_s = f"{view['bedrooms']} quartos" if view["bedrooms"] is not None else "-"
    area = view["area_m2"]
    area_s = f"{area:g}m2" if area is not None and area > 0 else "-"

    page, total_pages, idx_in_page, items_on_page = _page_info(index, total)
    counter = f"{idx_in_page + 1} de {items_on_page} - Pagina {page + 1} de {total_pages}"

    return (
        f"Imovel: {view['title']}\n"
        f"Preco: {view['price']} | Quartos: {bed_s} | Area: {area_s}\n"
        f"Bairro: {view['neighbourhood']} | {view['transaction_label']}\n\n"
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
            InlineKeyboardButton("< Anterior", callback_data=f"crs_{carousel_id}_prev")
        )
    if idx_in_page < items_on_page - 1:
        nav_row.append(
            InlineKeyboardButton("Proximo >", callback_data=f"crs_{carousel_id}_next")
        )

    page_row: list[InlineKeyboardButton] = []
    if page > 0:
        page_row.append(
            InlineKeyboardButton(
                "< Pagina anterior", callback_data=f"crs_{carousel_id}_pgp"
            )
        )
    if page < total_pages - 1:
        page_row.append(
            InlineKeyboardButton(
                "Proxima pagina >>", callback_data=f"crs_{carousel_id}_pgn"
            )
        )

    rows: list[list[InlineKeyboardButton]] = []
    if nav_row:
        rows.append(nav_row)
    if page_row:
        rows.append(page_row)
    if url is not None:
        rows.append([InlineKeyboardButton("Ver anuncio", url=url)])
    return InlineKeyboardMarkup(rows)


def _carousel_photo_url(ad: Ad) -> str | None:
    images = ad.get("images")
    if not isinstance(images, list) or not images:
        return None

    first_image = images[0]
    if photo_url := _valid_http_url(first_image):
        return photo_url
    if isinstance(first_image, dict):
        return _valid_http_url(
            first_image.get("originalWebp") or first_image.get("original")
        )
    return None


def _has_photo(ad: Ad) -> bool:
    return _carousel_photo_url(ad) is not None


def _properties_to_dict(props: object) -> dict[str, object]:
    """Normaliza properties do anuncio para um dict simples {campo: valor}."""
    if props is None:
        return {}

    data = props
    if isinstance(props, str):
        try:
            data = json.loads(props)
        except Exception:
            logger.debug("Falha ao decodificar properties: %r", props)
            return {}

    out: dict[str, object] = {}
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            for key, value in item.items():
                if isinstance(key, str):
                    out[key.strip().lower()] = value
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(key, str):
                out[key.strip().lower()] = value
    return out


def rooms_from_properties(props: object) -> int | None:
    return _normalize_int(_properties_to_dict(props).get("rooms"))


def area_m2_from_properties(props: object) -> float | None:
    return _normalize_float(_properties_to_dict(props).get("size"))


def _state_key(carousel_id: str) -> str:
    return f"carousel_{carousel_id}"


def _coerce_state(state: object) -> CarouselState | None:
    if not isinstance(state, dict):
        return None

    listings = state.get("listings")
    if not isinstance(listings, list) or not listings:
        return None

    index = _normalize_int(state.get("index"))
    chat_id = _normalize_int(state.get("chat_id"))
    is_photo = bool(state.get("is_photo"))

    if index is None or chat_id is None:
        return None

    return {
        "chat_id": chat_id,
        "listings": cast(list[Ad], listings),
        "index": index,
        "page_size": PAGE_SIZE,
        "is_photo": is_photo,
    }


async def send_carousel(
    bot: Bot,
    chat_id: int,
    ads: list[Ad],
    carousel_id: str,
    state_store: dict[str, object],
) -> None:
    """Envia a primeira pagina do carrossel e grava o estado em *state_store*."""
    if not ads:
        logger.warning("Carrossel %s nao enviado: lista de anuncios vazia.", carousel_id)
        return

    first_ad = ads[0]
    total = len(ads)
    view = _ad_view(first_ad)
    caption = _carousel_caption(view, 0, total)
    keyboard = _carousel_keyboard(carousel_id, 0, total, view["listing_url"])

    is_photo = False
    if view["photo_url"]:
        try:
            await bot.send_photo(
                chat_id=chat_id,
                photo=view["photo_url"],
                caption=caption,
                reply_markup=keyboard,
            )
            is_photo = True
        except TelegramError as exc:
            logger.warning(
                "send_photo falhou para %s (%s); caindo para texto.",
                carousel_id,
                exc,
            )
            await bot.send_message(chat_id=chat_id, text=caption, reply_markup=keyboard)
    else:
        await bot.send_message(chat_id=chat_id, text=caption, reply_markup=keyboard)

    state_store[_state_key(carousel_id)] = {
        "chat_id": chat_id,
        "listings": ads,
        "index": 0,
        "page_size": PAGE_SIZE,
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

    page = index // PAGE_SIZE
    if action == "next":
        return min(index + 1, total - 1)
    if action == "prev":
        return max(index - 1, 0)
    if action == "pgn":
        return min((page + 1) * PAGE_SIZE, total - 1)
    if action == "pgp":
        return max((page - 1) * PAGE_SIZE, 0)
    return index


async def _render_carousel_update(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    carousel_id: str,
    state: CarouselState,
) -> None:
    ads = state["listings"]
    total = len(ads)
    if total == 0:
        logger.warning("Carrossel %s ficou sem anuncios no estado.", carousel_id)
        return

    index = min(max(state["index"], 0), total - 1)
    state["index"] = index
    view = _ad_view(ads[index])
    caption = _carousel_caption(view, index, total)
    keyboard = _carousel_keyboard(carousel_id, index, total, view["listing_url"])
    was_photo = state["is_photo"]
    photo_url = view["photo_url"]

    try:
        if was_photo and photo_url:
            await query.edit_message_media(
                media=InputMediaPhoto(media=photo_url, caption=caption),
                reply_markup=keyboard,
            )
            state["is_photo"] = True
            return

        if not was_photo and not photo_url:
            await query.edit_message_text(text=caption, reply_markup=keyboard)
            state["is_photo"] = False
            return

        message = query.message
        if message is None:
            logger.warning("Mensagem ausente ao atualizar carrossel %s.", carousel_id)
            return

        chat_id = message.chat_id
        try:
            await message.delete()
        except TelegramError:
            logger.debug("Nao foi possivel apagar mensagem do carrossel %s", carousel_id)

        if photo_url:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo_url,
                caption=caption,
                reply_markup=keyboard,
            )
            state["is_photo"] = True
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=caption,
                reply_markup=keyboard,
            )
            state["is_photo"] = False
    except BadRequest as exc:
        logger.debug("Carrossel %s sem alteracao: %s", carousel_id, exc)
    except TelegramError:
        logger.exception("Erro ao renderizar carrossel %s", carousel_id)


async def carousel_nav_cb(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handler para os botoes Anterior/Proximo/Paginas do carrossel."""
    query = update.callback_query
    if query is None:
        return

    parsed = _parse_nav_callback(query.data or "")
    if parsed is None:
        await query.answer()
        return

    carousel_id, action = parsed
    bot_data = context.application.bot_data
    raw_state = bot_data.get(_state_key(carousel_id)) if bot_data is not None else None
    state = _coerce_state(raw_state)
    if state is None:
        logger.warning("Carrossel %s expirado ou com estado invalido.", carousel_id)
        await query.answer(
            "Carrossel expirado. Crie um novo alerta para ver os imoveis.",
            show_alert=False,
        )
        return

    current = min(max(state["index"], 0), len(state["listings"]) - 1)
    new_index = _next_index(current, action, len(state["listings"]))
    if new_index == current:
        await query.answer()
        return

    state["index"] = new_index
    if bot_data is not None:
        bot_data[_state_key(carousel_id)] = state

    await query.answer()
    await _render_carousel_update(query, context, carousel_id, state)


def register_handlers(app: Application) -> None:
    """Registra o ``CallbackQueryHandler`` de navegacao do carrossel."""
    app.add_handler(
        CallbackQueryHandler(
            carousel_nav_cb,
            pattern=r"^crs_.+_(?:next|prev|pgn|pgp)$",
        )
    )
