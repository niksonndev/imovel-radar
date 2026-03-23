"""
Carrossel de anúncios: exibe imóveis em mensagem interativa navegável.

send_carousel   — envia a primeira página e guarda estado em user_data
immediate_seed  — scrape imediato + seed seen_listings + carrossel
carousel_cb     — navega ◀ Anterior / Próximo ▶ / ✅ Concluir
"""
from __future__ import annotations

import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Update,
)
from telegram.ext import ContextTypes

from database import crud

logger = logging.getLogger(__name__)

MAX_CAROUSEL = 5
MAX_NOTIF_CAROUSEL = 10


def _fmt_money(v: float | None) -> str:
    if v is None:
        return "—"
    return f"R$ {v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _carousel_caption(ad: dict, index: int, total: int, transaction: str) -> str:
    title = ad.get("title") or "Imóvel"
    price = _fmt_money(ad.get("price"))
    bedrooms = ad.get("bedrooms")
    bed_s = f"{bedrooms} quartos" if bedrooms is not None else "—"
    area = ad.get("area_m2")
    area_s = f"{area:g}m²" if area else "—"
    neighborhood = ad.get("neighborhood") or "—"
    tr_label = {"sale": "Venda", "rent": "Aluguel"}.get(transaction, transaction or "")

    return (
        f"🏠 {title}\n"
        f"💰 {price} | 🛏 {bed_s} | 📐 {area_s}\n"
        f"📍 {neighborhood} · {tr_label}\n\n"
        f"{index + 1} de {total}"
    )


def _carousel_keyboard(
    carousel_id, index: int, total: int, url: str | None
) -> InlineKeyboardMarkup:
    nav_row: list[InlineKeyboardButton] = []
    if index > 0:
        nav_row.append(
            InlineKeyboardButton(
                "◀ Anterior", callback_data=f"crs_{carousel_id}_prev"
            )
        )
    if index < total - 1:
        nav_row.append(
            InlineKeyboardButton(
                "Próximo ▶", callback_data=f"crs_{carousel_id}_next"
            )
        )

    link_row = [
        InlineKeyboardButton("🔗 Ver anúncio", url=url or "https://www.olx.com.br")
    ]
    done_row = [
        InlineKeyboardButton("✅ Concluir", callback_data=f"crs_{carousel_id}_done")
    ]

    rows: list[list[InlineKeyboardButton]] = []
    if nav_row:
        rows.append(nav_row)
    rows.append(link_row)
    rows.append(done_row)
    return InlineKeyboardMarkup(rows)


def _has_photo(ad: dict) -> bool:
    thumb = ad.get("thumbnail")
    return bool(thumb and isinstance(thumb, str) and thumb.startswith("http"))


# ────────────────────── enviar carrossel (reutilizável) ──────────────────────


async def send_carousel(
    bot,
    chat_id: int,
    ads: list[dict],
    transaction: str,
    carousel_id: str,
    user_data: dict,
) -> None:
    """Envia a primeira página do carrossel e armazena estado em *user_data*."""
    total = len(ads)
    ad = ads[0]
    caption = _carousel_caption(ad, 0, total, transaction)
    keyboard = _carousel_keyboard(carousel_id, 0, total, ad.get("url"))

    is_photo = False
    if _has_photo(ad):
        try:
            await bot.send_photo(
                chat_id=chat_id,
                photo=ad["thumbnail"],
                caption=caption,
                reply_markup=keyboard,
            )
            is_photo = True
        except Exception:
            await bot.send_message(
                chat_id=chat_id, text=caption, reply_markup=keyboard
            )
    else:
        await bot.send_message(
            chat_id=chat_id, text=caption, reply_markup=keyboard
        )

    user_data[f"carousel_{carousel_id}"] = {
        "ads": ads,
        "index": 0,
        "transaction": transaction,
        "is_photo": is_photo,
    }


# ────────────────────── seed imediato ──────────────────────


async def immediate_seed(
    app, alert_id: int, tg_id: int, filters: dict, user_data: dict
) -> None:
    """Scrape → seed seen_listings → exibe carrossel (até MAX_CAROUSEL anúncios)."""
    session_factory = app.bot_data["session_factory"]
    scraper = app.bot_data["scraper"]
    bot = app.bot

    try:
        listings = await scraper.search_listings(filters, max_pages=15)
    except Exception:
        logger.exception("Seed imediato falhou para alerta %s", alert_id)
        try:
            await bot.send_message(
                chat_id=tg_id,
                text="⚠️ Não consegui buscar imóveis agora. "
                "Vou tentar na próxima verificação automática. 🔔",
            )
        except Exception:
            pass
        return

    async with session_factory() as session:
        for ad in listings:
            oid = ad.get("olx_id")
            if oid:
                await crud.mark_seen(session, alert_id, oid)
        await crud.update_alert_last_checked(session, alert_id)

    transaction = filters.get("transaction", "sale")
    carousel_ads = listings[:MAX_CAROUSEL]

    if not carousel_ads:
        await bot.send_message(
            chat_id=tg_id,
            text=(
                "🔍 Nenhum imóvel encontrado com esses filtros no momento.\n"
                "Vou te avisar quando aparecer algo novo. 🔔"
            ),
        )
        return

    await send_carousel(
        bot, tg_id, carousel_ads, transaction, str(alert_id), user_data
    )


# ────────────────────── navegação do carrossel ──────────────────────

_DONE_TEXT = "✅ Pronto! Vou te avisar quando aparecer algo novo. 🔔"


async def carousel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para ◀ Anterior / Próximo ▶ / ✅ Concluir."""
    q = update.callback_query
    await q.answer()

    data = q.data or ""
    parts = data.split("_")
    if len(parts) < 3:
        return

    action = parts[-1]
    carousel_id = "_".join(parts[1:-1])
    key = f"carousel_{carousel_id}"
    carousel = context.user_data.get(key)

    if not carousel:
        try:
            await q.edit_message_text("Carrossel expirado.")
        except Exception:
            try:
                await q.edit_message_caption(
                    caption="Carrossel expirado.", reply_markup=None
                )
            except Exception:
                pass
        return

    # ── Concluir: sempre texto simples, sem foto, sem botões ──
    if action == "done":
        if carousel.get("is_photo"):
            chat_id = q.message.chat_id
            try:
                await q.message.delete()
            except Exception:
                pass
            try:
                await context.bot.send_message(chat_id=chat_id, text=_DONE_TEXT)
            except Exception:
                pass
        else:
            try:
                await q.edit_message_text(text=_DONE_TEXT)
            except Exception:
                pass
        context.user_data.pop(key, None)
        return

    # ── Navegação ──
    ads = carousel["ads"]
    current_idx = carousel["index"]
    transaction = carousel["transaction"]
    total = len(ads)

    if action == "next":
        new_idx = min(current_idx + 1, total - 1)
    elif action == "prev":
        new_idx = max(current_idx - 1, 0)
    else:
        return

    if new_idx == current_idx:
        return

    carousel["index"] = new_idx
    ad = ads[new_idx]

    caption = _carousel_caption(ad, new_idx, total, transaction)
    keyboard = _carousel_keyboard(carousel_id, new_idx, total, ad.get("url"))
    photo = _has_photo(ad)
    was_photo = carousel.get("is_photo", False)

    # Mesmo tipo → edita in-place
    if photo and was_photo:
        try:
            await q.edit_message_media(
                media=InputMediaPhoto(media=ad["thumbnail"], caption=caption),
                reply_markup=keyboard,
            )
            return
        except Exception as e:
            logger.warning("edit_message_media falhou: %s", e)

    if not photo and not was_photo:
        try:
            await q.edit_message_text(text=caption, reply_markup=keyboard)
            return
        except Exception as e:
            logger.warning("edit_message_text falhou: %s", e)

    # Tipo mudou (foto↔texto) — deleta e re-envia
    chat_id = q.message.chat_id
    try:
        await q.message.delete()
    except Exception:
        pass

    if photo:
        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=ad["thumbnail"],
                caption=caption,
                reply_markup=keyboard,
            )
            carousel["is_photo"] = True
            return
        except Exception:
            pass

    await context.bot.send_message(
        chat_id=chat_id, text=caption, reply_markup=keyboard
    )
    carousel["is_photo"] = False
