"""Handlers de callback para botões inline."""

from __future__ import annotations

import logging

from telegram import InputMediaPhoto, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot import keyboards
from bot.carousel import (
    PAGE_SIZE,
    _carousel_caption,
    _carousel_keyboard,
    _carousel_photo_url,
)

logger = logging.getLogger(__name__)


async def menu_home_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra o menu principal sem depender de /start."""
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(
        "🏠 *Menu principal*\nEscolha uma opção:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def menu_meus_alertas_cb(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Callback do botão '📋 Meus Alertas' com ações inline."""
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(
        "📋 Meus alertas está temporariamente indisponível no momento.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.home_keyboard(),
    )


async def alert_toggle_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde ao callback de pausar/reativar alerta."""
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    try:
        int(data.rsplit("_", 1)[-1])
    except ValueError:
        await q.message.reply_text(
            "ID de alerta inválido. Confira e tente novamente.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.home_keyboard(),
        )
        return

    await q.message.reply_text(
        "⏸️ Ação de pausar/reativar está temporariamente indisponível.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def alert_delete_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde ao callback de remover alerta."""
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    try:
        int(data.rsplit("_", 1)[-1])
    except ValueError:
        await q.message.reply_text(
            "ID de alerta inválido. Confira e tente novamente.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.home_keyboard(),
        )
        return

    await q.message.reply_text(
        "🗑️ Ação de deletar alerta está temporariamente indisponível.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def menu_ajuda_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback do botão '❓ Ajuda' (manda texto de comandos)."""
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(
        "*Como usar sem digitar comandos*\n\n"
        "Use os botões do menu principal para criar e gerenciar alertas, "
        "acompanhar anúncios, abrir watchlist e ver status.\n\n"
        "Você pode voltar ao menu principal pelos botões em cada tela.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.home_keyboard(),
    )


async def menu_watchlist_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde ao callback do menu de watchlist."""
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(
        "👀 Watchlist está temporariamente indisponível no momento.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.home_keyboard(),
    )


async def watch_remove_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde ao callback de remover item da watchlist."""
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    try:
        int(data.rsplit("_", 1)[-1])
    except ValueError:
        await q.message.reply_text(
            "ID da watchlist inválido. Confira e tente novamente.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.home_keyboard(),
        )
        return

    await q.message.reply_text(
        "🧹 Ação de remover da watchlist está temporariamente indisponível.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def menu_status_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra status resumido quando acionado por botão."""
    q = update.callback_query
    await q.answer()
    watch_days = context.application.bot_data.get("watch_days", 1)
    next_a = context.application.bot_data.get("next_alert_run")
    next_w = context.application.bot_data.get("next_watch_run")
    na = next_a.strftime("%d/%m %H:%M") if next_a else "—"
    nw = next_w.strftime("%d/%m %H:%M") if next_w else "—"
    await q.message.reply_text(
        f"*Status*\n"
        f"• Scrape/alertas: diariamente às *05:00* (Maceió) (próx.: _{na}_)\n"
        f"• Watchlist: a cada *{watch_days}* dia(s) (próx.: _{nw}_)\n"
        f"• Região: Maceió/AL",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.home_keyboard(),
    )


async def carousel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para ◀/▶ (anúncio) e ◀ Página/⏭ Página."""
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
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    ads = carousel["listings"]
    current_idx = carousel["index"]
    total = len(ads)

    page = current_idx // PAGE_SIZE
    page_start = page * PAGE_SIZE
    page_end = min(page_start + PAGE_SIZE, total)

    if action == "next":
        new_idx = min(current_idx + 1, page_end - 1)
    elif action == "prev":
        new_idx = max(current_idx - 1, page_start)
    elif action == "pgn":
        new_idx = min((page + 1) * PAGE_SIZE, total - 1)
    elif action == "pgp":
        new_idx = max((page - 1) * PAGE_SIZE, 0)
    else:
        return

    if new_idx == current_idx:
        return

    carousel["index"] = new_idx
    ad = ads[new_idx]

    caption = _carousel_caption(ad, new_idx, total)
    keyboard = _carousel_keyboard(carousel_id, new_idx, total, ad.get("url"))
    photo_url = _carousel_photo_url(ad)
    photo = photo_url is not None
    was_photo = carousel.get("is_photo", False)

    if photo and was_photo:
        try:
            await q.edit_message_media(
                media=InputMediaPhoto(media=photo_url, caption=caption),
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

    chat_id = q.message.chat_id
    try:
        await q.message.delete()
    except Exception:
        pass

    if photo and photo_url:
        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo_url,
                caption=caption,
                reply_markup=keyboard,
            )
            carousel["is_photo"] = True
            return
        except Exception:
            pass

    await context.bot.send_message(chat_id=chat_id, text=caption, reply_markup=keyboard)
    carousel["is_photo"] = False
