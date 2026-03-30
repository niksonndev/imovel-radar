"""
Carrossel de anúncios: exibe imóveis em mensagem interativa navegável.

Paginação em grupos de PAGE_SIZE (5). Navegação anúncio-a-anúncio dentro
da página e salto entre páginas.

send_carousel   — envia a primeira página e guarda estado em user_data
immediate_seed  — scrape imediato + seed seen_listings + carrossel
"""

from __future__ import annotations

import json
import logging
import math

from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import Application

from bot import keyboards
from database import get_connection
from utils.pricing import price_value_to_float

logger = logging.getLogger(__name__)

PAGE_SIZE = 10
MAX_NOTIF_CAROUSEL = 10


def _fmt_money(v: float | None) -> str:
    if v is None:
        return "—"
    return f"R$ {v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _ad_price_caption(ad: dict) -> str:
    pv = ad.get("priceValue")
    if isinstance(pv, str) and pv.strip():
        return pv.strip()
    p = ad.get("price")
    if p is not None:
        return _fmt_money(float(p))
    return _fmt_money(price_value_to_float(pv))


def _page_info(index: int, total: int) -> tuple[int, int, int, int]:
    """Retorna (page 0-based, total_pages, idx_in_page, items_on_page)."""
    page = index // PAGE_SIZE
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    page_start = page * PAGE_SIZE
    items_on_page = min(PAGE_SIZE, total - page_start)
    idx_in_page = index - page_start
    return page, total_pages, idx_in_page, items_on_page


def _carousel_caption(ad: dict, index: int, total: int, transaction: str) -> str:
    title = ad.get("title") or "Imóvel"
    price = _ad_price_caption(ad)
    bedrooms = ad.get("bedrooms")
    if bedrooms is None:
        bedrooms = rooms_from_properties(ad.get("properties"))
    bed_s = f"{bedrooms} quartos" if bedrooms is not None else "—"
    area = ad.get("area_m2")
    if area is None:
        area = area_m2_from_properties(ad.get("properties"))
    area_s = f"{area:g}m²" if area else "—"
    neighborhood = ad.get("neighbourhood") or ad.get("neighborhood") or "—"
    tr_label = {"sale": "Venda", "rent": "Aluguel"}.get(transaction, transaction or "")

    page, total_pages, idx_in_page, items_on_page = _page_info(index, total)
    counter = (
        f"{idx_in_page + 1} de {items_on_page} — Página {page + 1} de {total_pages}"
    )

    return (
        f"🏠 {title}\n"
        f"💰 {price} | 🛏 {bed_s} | 📐 {area_s}\n"
        f"📍 {neighborhood} · {tr_label}\n\n"
        f"{counter}"
    )


def _carousel_keyboard(
    carousel_id: str, index: int, total: int, url: str | None
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

    link_row = [
        InlineKeyboardButton("🔗 Ver anúncio", url=url or "https://www.olx.com.br")
    ]

    rows: list[list[InlineKeyboardButton]] = []
    if nav_row:
        rows.append(nav_row)
    if page_row:
        rows.append(page_row)
    rows.append(link_row)
    return InlineKeyboardMarkup(rows)


def _carousel_photo_url(ad: dict) -> str | None:
    t = ad.get("thumbnail")
    if isinstance(t, str) and t.startswith("http"):
        return t
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


def _filter_cached_ads(ads: list[dict], filters: dict) -> list[dict]:
    """Aplica filtros locais do alerta sobre anúncios vindos do cache."""
    pmin = filters.get("price_min")
    pmax = filters.get("price_max")
    bmin = filters.get("bedrooms_min")
    amin = filters.get("area_min")
    amax = filters.get("area_max")
    neighborhoods = [n.lower() for n in (filters.get("neighborhoods") or [])]

    out: list[dict] = []
    for ad in ads:
        ad_price = ad.get("price")
        if ad_price is None:
            ad_price = price_value_to_float(ad.get("priceValue"))
        if pmin is not None and ad_price is not None and ad_price < pmin:
            continue
        if pmax is not None and ad_price is not None and ad_price > pmax:
            continue
        rooms = ad.get("bedrooms")
        if rooms is None:
            rooms = rooms_from_properties(ad.get("properties"))
        if bmin is not None and rooms is not None and rooms < bmin:
            continue
        area = ad.get("area_m2")
        if area is None:
            area = area_m2_from_properties(ad.get("properties"))
        if amin is not None and area is not None and area < amin:
            continue
        if amax is not None and area is not None and area > amax:
            continue
        if neighborhoods:
            loc = ad.get("neighbourhood") or ad.get("neighborhood") or ""
            blob = ((ad.get("title") or "") + " " + loc).lower()
            if not any(n in blob for n in neighborhoods):
                continue
        out.append(ad)
    return out


def _load_active_listings_from_db(limit: int = 300) -> list[dict]:
    """Carrega anúncios ativos do cache local (SQLite)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT listId, url, title, priceValue, oldPrice, municipality,
                   neighbourhood, category, images, properties
            FROM listings
            WHERE active = 1
            ORDER BY listId DESC
            LIMIT ?;
            """,
            (limit,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    listings: list[dict] = []
    for row in rows:
        ad = dict(row)
        images = ad.get("images")
        if isinstance(images, str) and images.strip():
            try:
                parsed = json.loads(images)
                ad["images"] = parsed if isinstance(parsed, list) else []
            except Exception:
                ad["images"] = []
        else:
            ad["images"] = []
        listings.append(ad)
    return listings


# ────────────────────── enviar carrossel (reutilizável) ──────────────────────


async def send_carousel(
    bot: Bot,
    chat_id: int,
    ads: list[dict],
    transaction: str,
    carousel_id: str,
    user_data: dict[str, object],
) -> None:
    """Envia a primeira página do carrossel e armazena estado em *user_data*."""
    if not ads:
        return

    total = len(ads)
    ad = ads[0]
    caption = _carousel_caption(ad, 0, total, transaction)
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
        except Exception:
            await bot.send_message(chat_id=chat_id, text=caption, reply_markup=keyboard)
    else:
        await bot.send_message(chat_id=chat_id, text=caption, reply_markup=keyboard)

    user_data[f"carousel_{carousel_id}"] = {
        "listings": ads,
        "index": 0,
        "transaction": transaction,
        "page_size": PAGE_SIZE,
        "is_photo": is_photo,
    }


# ────────────────────── seed imediato ──────────────────────


async def immediate_seed(
    app: Application,
    alert_id: int,
    tg_id: int,
    filters: dict[str, object],
    user_data: dict[str, object],
) -> None:
    """Seed imediato usando cache diário no banco + filtro local + carrossel."""
    bot = app.bot

    try:
        listings = _load_active_listings_from_db()
        listings = _filter_cached_ads(listings, filters)
    except Exception:
        logger.exception(
            "Seed imediato via cache local falhou para alerta %s", alert_id
        )
        try:
            await bot.send_message(
                chat_id=tg_id,
                text="⚠️ Não consegui consultar o cache de imóveis agora. "
                "Vou tentar na próxima verificação automática. 🔔",
            )
        except Exception:
            pass
        return

    transaction = filters.get("transaction", "sale")

    if not listings:
        await bot.send_message(
            chat_id=tg_id,
            text=(
                "🔍 Nenhum imóvel encontrado com esses filtros no momento.\n"
                "Vou te avisar quando aparecer algo novo. 🔔"
            ),
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return

    await send_carousel(bot, tg_id, listings, transaction, str(alert_id), user_data)
    await bot.send_message(
        chat_id=tg_id,
        text="✅ Alerta criado! Vou te avisar quando aparecer algo novo. 🔔",
        reply_markup=keyboards.main_menu_keyboard(),
    )


