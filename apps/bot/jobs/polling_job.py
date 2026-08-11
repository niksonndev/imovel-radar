"""
Job de polling que verifica listings não notificados no scraper periodicamente (padrão: 1 hora).

Fluxo:
1. Consulta ``GET /listings/{chat_id}/unnotified`` para cada chat_id registrado
2. Se há listings, envia carrossel e marca como notificados
   via ``POST /listings/{chat_id}/mark-notified``
"""

from __future__ import annotations

import asyncio
import logging

from shared_models.api_schemas import NotifiedPair
from shared_models.models import Listing
from telegram.ext import Application

from handlers.api_client import get_unnotified_listings, mark_listings_notified
from handlers.carousel import send_carousel

logger = logging.getLogger(__name__)


async def notify_new_matches(app: Application) -> None:
    """Verifica listings não notificados por chat, envia carrossel e marca como notificados."""
    chat_ids = list(app.bot_data.get("polling_chat_ids", []))
    if not chat_ids:
        logger.info("Polling: nenhum chat_id registrado")
        return

    for chat_id in chat_ids:
        try:
            await _process_chat(chat_id, app)
        except Exception:
            logger.exception("Polling: falha ao processar chat %s", chat_id)
        await asyncio.sleep(2)  # evita flood no Telegram

    logger.info("Polling: %s chat(s) processado(s)", len(chat_ids))


async def _process_chat(chat_id: int, app: Application) -> None:
    """Busca listings não notificados de um chat, envia carrossel e marca como notificados."""
    resp = await get_unnotified_listings(chat_id)
    listings: list[Listing] = [item for item in resp.listings]
    if not listings:
        logger.info("Polling: chat %s sem listings não notificados", chat_id)
        return

    await send_carousel(
        app.bot,
        chat_id,
        listings,
        str(chat_id),
        app.bot_data,
    )

    pairs: list[NotifiedPair] = [
        NotifiedPair(alert_id=item.alert_id, listing_id=item.listing_id)
        for item in resp.listings
    ]

    await mark_listings_notified(chat_id, pairs)
    logger.info(
        "Polling: chat %s — %s listings marcados como notificados",
        chat_id,
        len(pairs),
    )
