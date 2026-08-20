"""
Job de notificação que verifica listings não notificados e envia carrosséis.

Re-homeado para rodar via EventBridge (ADR 0004) ou no dev via JobQueue. Lê os
chat_ids diretamente do Postgres (ADR 0005) — não usa mais app.bot_data.
"""

from __future__ import annotations

import asyncio
import logging

from shared_models.api_schemas import NotifiedPair
from sqlmodel import Session
from telegram.ext import Application

from database import queries
from database.db import engine
from handlers.api_client import get_unnotified_listings, mark_listings_notified
from handlers.carousel import send_carousel

logger = logging.getLogger(__name__)


async def notify_new_matches(app: Application) -> None:
    """Verifica listings não notificados por chat, envia carrossel e marca."""
    chat_ids = list_all_users()
    if not chat_ids:
        logger.info("Notificação: nenhum chat cadastrado")
        return

    for chat_id in chat_ids:
        try:
            await _process_chat(chat_id, app)
        except Exception:
            logger.exception("Notificação: falha ao processar chat %s", chat_id)
        await asyncio.sleep(2)  # evita flood no Telegram

    logger.info("Notificação: %s chat(s) processado(s)", len(chat_ids))


def list_all_users() -> list[int]:
    """Todos os chat_ids cadastrados no Postgres."""
    with Session(engine) as session:
        return queries.get_users_chat_ids(session)


async def _process_chat(chat_id: int, app: Application) -> None:
    """Busca listings não notificados de um chat, envia carrossel e marca."""
    resp = await get_unnotified_listings(chat_id)
    if not resp.listings:
        logger.info("Notificação: chat %s sem listings não notificados", chat_id)
        return

    await send_carousel(
        app.bot,
        chat_id,
        [item for item in resp.listings],
        str(chat_id),
        app.bot_data,
    )

    pairs = [
        NotifiedPair(alert_id=item.alert_id, listing_id=item.listing_id)
        for item in resp.listings
    ]
    await mark_listings_notified(chat_id, pairs)
    logger.info("Notificação: chat %s — %s listings marcados", chat_id, len(pairs))

