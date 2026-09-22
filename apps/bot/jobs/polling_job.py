"""
Job de notificação que verifica listings não notificados e envia carrosséis.

Re-homeado para rodar via EventBridge diário (2h após o scrape; ADR 0004) ou
no dev via JobQueue. Lê os chat_ids diretamente do Postgres (ADR 0005) — não
usa mais app.bot_data.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from sqlmodel import Session
from telegram.constants import ParseMode
from telegram.ext import Application

from database import queries
from database.db import get_engine
from handlers.carousel import send_carousel
from handlers.data import (
    get_changed_watches,
    get_unnotified_listings,
    mark_listings_notified,
    update_watch_baselines,
)
from handlers.ui import menus

logger = logging.getLogger(__name__)


async def notify_new_matches(app: Application, *, dry_run: bool = False) -> None:
    """Verifica listings não notificados por chat, envia carrossel e marca."""
    chat_ids = list_all_users()
    if not chat_ids:
        logger.info("Notificação: nenhum chat cadastrado")
        return

    for chat_id in chat_ids:
        try:
            await _process_chat(chat_id, app, dry_run=dry_run)
        except Exception:
            logger.exception("Notificação: falha ao processar chat %s", chat_id)
        if not dry_run:
            await asyncio.sleep(2)  # evita flood no Telegram

    logger.info(
        "Notificação%s: %s chat(s) processado(s)",
        " dry-run" if dry_run else "",
        len(chat_ids),
    )


async def notify_watched_changes(app: Application, *, dry_run: bool = False) -> None:
    """Avisa mudanças de preço / status em anúncios acompanhados."""
    try:
        changes = await get_changed_watches()
    except Exception:
        logger.exception("Watchlist: falha ao buscar mudanças")
        return

    if not changes:
        logger.info("Watchlist: nenhuma mudança pendente")
        return

    by_chat: dict[int, list] = defaultdict(list)
    for row in changes:
        by_chat[row.watch.chat_id].append(row)

    for chat_id, rows in by_chat.items():
        try:
            await _process_watch_chat(chat_id, rows, app, dry_run=dry_run)
        except Exception:
            logger.exception("Watchlist: falha ao processar chat %s", chat_id)
        if not dry_run:
            await asyncio.sleep(2)

    logger.info(
        "Watchlist%s: %s chat(s) processado(s)",
        " dry-run" if dry_run else "",
        len(by_chat),
    )


async def run_daily_notifications(app: Application, *, dry_run: bool = False) -> None:
    """Pipeline diário: matches de alerta + mudanças na watchlist."""
    if dry_run:
        logger.info("Notificação: dry-run (sem Telegram nem mark)")
    await notify_new_matches(app, dry_run=dry_run)
    await notify_watched_changes(app, dry_run=dry_run)


def list_all_users() -> list[int]:
    """Todos os chat_ids cadastrados no Postgres."""
    with Session(get_engine()) as session:
        return queries.get_users_chat_ids(session)


async def _process_chat(chat_id: int, app: Application, *, dry_run: bool = False) -> None:
    """Busca listings não notificados de um chat, envia carrossel e marca."""
    rows = await get_unnotified_listings(chat_id)
    if not rows:
        logger.info("Notificação: chat %s sem listings não notificados", chat_id)
        return

    if dry_run:
        logger.info(
            "Notificação dry-run: chat %s — %s listings (não enviados/marcados)",
            chat_id,
            len(rows),
        )
        return

    await send_carousel(
        app.bot,
        chat_id,
        [row.listing for row in rows],
        str(chat_id),
        app.bot_data,
    )

    # Mark immediately after send so a later failure cannot re-notify.
    pairs = [(row.alert_id, row.listing.listing_id) for row in rows]
    await mark_listings_notified(chat_id, pairs)
    logger.info("Notificação: chat %s — %s listings marcados", chat_id, len(pairs))


async def _process_watch_chat(
    chat_id: int, rows: list, app: Application, *, dry_run: bool = False
) -> None:
    baselines: list[tuple[int, int | None, bool]] = []

    for row in rows:
        watch = row.watch
        listing = row.listing
        if watch.id is None:
            continue

        messages: list[str] = []
        if listing.price_value != watch.last_known_price:
            messages.append(
                menus.watchlist_change_price_message(
                    title=listing.title or "",
                    old_price=watch.last_known_price,
                    new_price=listing.price_value,
                    url=listing.url,
                )
            )
        if listing.active != watch.last_known_active:
            if not listing.active:
                messages.append(
                    menus.watchlist_change_removed_message(
                        title=listing.title or "",
                        url=listing.url,
                    )
                )
            else:
                messages.append(
                    menus.watchlist_change_reactivated_message(
                        title=listing.title or "",
                        url=listing.url,
                    )
                )

        if dry_run:
            logger.info(
                "Watchlist dry-run: chat %s watch %s — %s mudança(s) (não enviadas)",
                chat_id,
                watch.id,
                len(messages),
            )
            continue

        for text in messages:
            await app.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
            await asyncio.sleep(0.5)

        baselines.append((watch.id, listing.price_value, listing.active))

    if baselines:
        await update_watch_baselines(baselines)
        logger.info("Watchlist: chat %s — %s baseline(s) atualizado(s)", chat_id, len(baselines))
