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

from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.error import TelegramError
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from utils.pricing import format_brl
from hydrator import HydratedListing
from models import Properties

logger = logging.getLogger(__name__)

PAGE_SIZE = 10
MAX_TITLE_LEN = 80
CAROUSEL_CALLBACK_PREFIX = "crs_"

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


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _carousel_caption(listing: HydratedListing, index: int, total: int) -> str:
    props: Properties = {}
    for item in listing["properties"]:
        props.update(item)

    title = _truncate(listing["title"], MAX_TITLE_LEN)
    price = format_brl(listing["priceValue"])
    bedrooms = props.get("rooms")
    bedrooms_label = f"{bedrooms} quarto(s)" if bedrooms is not None else "—"
    area = props.get("size")
    area_label = f"{area:g}m²" if area else "—"
    neighbourhood = listing["neighbourhood"] or "—"
    rental_or_sale = props.get("real_estate_type", "—")

    page, total_pages, idx_in_page, items_on_page = _page_info(index, total)
    counter = (
        f"{idx_in_page + 1} de {items_on_page} - Pagina {page + 1} de {total_pages}"
    )

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


# ────────────────────── enviar carrossel ──────────────────────


def _state_key(carousel_id: str) -> str:
    return f"carousel_{carousel_id}"


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
    """

    total = len(listings)
    listing = listings[0]
    caption = _carousel_caption(listing, 0, total)
    keyboard = _carousel_keyboard(carousel_id, 0, total, listing.get("url"))

    photo_url = _carousel_photo_url(listing)
    if photo_url:
        try:
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo_url,
                caption=caption,
                reply_markup=keyboard,
            )
            return
        except TelegramError as e:
            logger.warning(
                "send_photo falhou para %s (%s); caindo para texto.", carousel_id, e
            )

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
