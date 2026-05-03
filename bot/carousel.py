"""
Carrossel de anuncios: camada de apresentacao pura.

Recebe uma ``list[dict]`` já pronta (preparada por ``bot.alert_matching`` ou
por outro orquestrador) e renderiza no Telegram como uma sequência paginada
de mensagens com foto (quando disponível) e teclado inline.

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

Helpers como ``rooms_from_properties`` / ``area_m2_from_properties``
normalizam o JSON de ``properties`` vindo do banco sob demanda.
"""

from __future__ import annotations

import json
import logging
import math

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


# ────────────────────── helpers de paginação/legenda ──────────────────────


def _page_info(index: int, total: int) -> tuple[int, int, int, int]:
    """Retorna (page 0-based, total_pages, idx_in_page, items_on_page)."""
    safe_total = max(total, 0)
    safe_index = _clamp_index(index, safe_total)
    total_pages = max(1, (safe_total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = safe_index // PAGE_SIZE
    page_start = page * PAGE_SIZE
    items_on_page = min(PAGE_SIZE, total - page_start)
    idx_in_page = index - page_start
    return page, total_pages, idx_in_page, items_on_page


def _transaction_label(ad: dict) -> str:
    """Deriva o rótulo (Aluguel/Venda) a partir de ``category`` do anúncio."""
    category = (ad.get("category") or "").lower()
    if "sale" in category or "venda" in category:
        return "Venda"
    return "Aluguel"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _carousel_caption(ad: dict, index: int, total: int) -> str:
    title = _truncate(ad.get("title") or "Imóvel", MAX_TITLE_LEN)
    price = format_brl(ad.get("priceValue"))
    bedrooms = ad.get("bedrooms")
    if bedrooms is None:
        bedrooms = rooms_from_properties(ad.get("properties"))
    bed_s = f"{bedrooms} quartos" if bedrooms is not None else "—"
    area = ad.get("area_m2")
    if area is None:
        area = area_m2_from_properties(ad.get("properties"))
    area_s = f"{area:g}m²" if area else "—"
    neighborhood = ad.get("neighbourhood") or ad.get("neighborhood") or "—"
    tr_label = _transaction_label(ad)

    page, total_pages, idx_in_page, items_on_page = _page_info(index, total)
    counter = (
        f"{idx_in_page + 1} de {items_on_page} - Pagina {page + 1} de {total_pages}"
    )

    return (
        f"🏠 {title}\n"
        f"💰 {price} | 🛏 {bed_s} | 📐 {area_s}\n"
        f"📍 {neighborhood} · {tr_label}\n\n"
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
            InlineKeyboardButton("◀ Anterior", callback_data=f"crs_{carousel_id}_prev")
        )
    if idx_in_page < items_on_page - 1:
        nav_row.append(
            InlineKeyboardButton("Próximo ▶", callback_data=f"crs_{carousel_id}_next")
        )

    page_row: list[InlineKeyboardButton] = []
    if page > 0:
        page_row.append(
            InlineKeyboardButton(
                "◀ Página anterior", callback_data=f"crs_{carousel_id}_pgp"
            )
        )
    if page < total_pages - 1:
        page_row.append(
            InlineKeyboardButton(
                "⏭ Próxima página", callback_data=f"crs_{carousel_id}_pgn"
            )
        )

    rows: list[list[InlineKeyboardButton]] = []
    if nav_row:
        rows.append(nav_row)
    if page_row:
        rows.append(page_row)
    # Só oferece o link quando o anúncio realmente tem URL válida;
    # evita mandar o usuário para a home da OLX por engano.
    if isinstance(url, str) and url.startswith("http"):
        rows.append([InlineKeyboardButton("🔗 Ver anúncio", url=url)])
    return InlineKeyboardMarkup(rows)


def _carousel_photo_url(ad: dict) -> str | None:
    imgs = ad.get("images")
    if isinstance(imgs, list) and imgs:
        u = imgs[0]
        if isinstance(u, str) and u.startswith("http"):
            return u
        if isinstance(u, dict):
            w = u.get("originalWebp") or u.get("original")
            if isinstance(w, str) and w.startswith("http"):
                return w
    return None


def _has_photo(ad: dict) -> bool:
    return _carousel_photo_url(ad) is not None


# ────────────────────── normalização de ``properties`` ──────────────────────


def _properties_to_dict(props: object) -> dict[str, object]:
    """Normaliza properties do anúncio para um dict simples {campo: valor}."""
    if props is None:
        return {}

    data = props
    if isinstance(props, str):
        try:
            data = json.loads(props)
        except Exception:
            return {}

    out: dict[str, object] = {}
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            for k, v in item.items():
                if isinstance(k, str):
                    out[k.strip().lower()] = v
    elif isinstance(data, dict):
        for k, v in data.items():
            if isinstance(k, str):
                out[k.strip().lower()] = v
    return out


def rooms_from_properties(props: object) -> int | None:
    p = _properties_to_dict(props)
    value = p.get("rooms")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def area_m2_from_properties(props: object) -> float | None:
    p = _properties_to_dict(props)
    value = p.get("size")
    if isinstance(value, int):
        return float(value)
    if isinstance(value, float):
        return value
    return None


# ────────────────────── enviar carrossel ──────────────────────


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
    ads: list[dict],
    carousel_id: str,
    state_store: MutableMapping[str, object],
) -> None:
    """Envia a primeira página do carrossel e grava o estado em *state_store*.

    *state_store* deve ser o mesmo dict lido pelo handler de navegação —
    normalmente ``app.bot_data``. O ``carousel_id`` deve ser **globalmente
    único** (ex.: ``str(alert_id)`` para o seed, ``f"{alert_id}n"`` para
    notificação recorrente), já que a chave ``carousel_<id>`` é compartilhada.
    """
    if not ads:
        return

    total = len(ads)
    ad = ads[0]
    caption = _carousel_caption(ad, 0, total)
    keyboard = _carousel_keyboard(carousel_id, 0, total, ad.get("url"))

    is_photo = False
    photo_url = _carousel_photo_url(ad)
    if photo_url:
        try:
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo_url,
                caption=caption,
                reply_markup=keyboard,
            )
            is_photo = True
        except TelegramError as e:
            logger.warning(
                "send_photo falhou para %s (%s); caindo para texto.", carousel_id, e
            )
            await bot.send_message(chat_id=chat_id, text=caption, reply_markup=keyboard)
    else:
        await bot.send_message(chat_id=chat_id, text=caption, reply_markup=keyboard)

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
    page = index // PAGE_SIZE
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
    index: int = state["index"]
    ad = ads[index]
    caption = _carousel_caption(ad, index, total)
    keyboard = _carousel_keyboard(carousel_id, index, total, ad.get("url"))
    was_photo: bool = bool(state.get("is_photo"))
    photo_url = _carousel_photo_url(ad)

    try:
        if was_photo and has_photo:
            await query.edit_message_media(
                media=InputMediaPhoto(media=photo_url, caption=caption),
                reply_markup=keyboard,
            )
            state["is_photo"] = True
        elif not was_photo and not photo_url:
            await query.edit_message_text(text=caption, reply_markup=keyboard)
            state["is_photo"] = False
        else:
            # Muda o tipo de mídia (texto↔foto): Telegram não permite editar
            # entre tipos diferentes, então apaga e reenvia.
            chat_id = query.message.chat_id
            try:
                await query.message.delete()
            except TelegramError:
                logger.debug(
                    "Não foi possível apagar mensagem do carrossel %s", carousel_id
                )
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
                    chat_id=chat_id, text=caption, reply_markup=keyboard
                )
                state["is_photo"] = False
    except BadRequest as e:
        # Principal caso: "message is not modified" quando o conteúdo não mudou.
        logger.debug("Carrossel %s sem alteração: %s", carousel_id, e)
    except TelegramError:
        logger.exception("Erro ao renderizar carrossel %s", carousel_id)


async def carousel_nav_cb(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handler para os botões Anterior/Próximo/Páginas do carrossel.

    Lê o estado de ``context.application.bot_data`` (onde ``send_carousel``
    gravou). Isso permite que tanto carrosséis do wizard quanto os disparados
    pelo scheduler compartilhem o mesmo fluxo de navegação.
    """
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
    if not isinstance(state, dict) or not state.get("listings"):
        await query.answer(
            "Carrossel expirado. Crie um novo alerta para ver os imoveis.",
            show_alert=False,
        )
        return

    total = len(state["listings"])
    current: int = int(state.get("index", 0))
    new_index = _next_index(current, action, total)
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
