"""
Job de polling que verifica matches novos no scraper periodicamente (padrão: 1 hora).

Fluxo:
1. Consulta ``GET /alerts/active`` no scraper
2. Para cada alerta ativo, consulta ``GET /alerts/{id}/matches``
3. Se há matches, envia carrossel via bot e marca como notificados
"""

from __future__ import annotations

import asyncio
import logging

from telegram import Bot
from telegram.ext import Application

from handlers.api_client import ScraperAPI
from handlers.carousel import send_carousel

logger = logging.getLogger(__name__)


async def notify_new_matches(app: Application) -> None:
    """Percorre todos os alertas ativos e notifica matches novos."""
    api = ScraperAPI()
    try:
        alerts_resp = await api.get_active_alerts()
        alerts = alerts_resp.alerts
    except Exception:
        logger.exception("Polling: falha ao buscar alertas ativos")
        return
    finally:
        await api.close()

    if not alerts:
        logger.info("Polling: nenhum alerta ativo")
        return

    for alert in alerts:
        try:
            await _process_alert(app.bot, alert.id, alert.user_id, api, app.bot_data)  # type: ignore[arg-type]
        except Exception:
            logger.exception("Polling: falha ao processar alerta %s", alert.id)
        await asyncio.sleep(2)  # evita flood no Telegram

    logger.info("Polling: %s alerta(s) processado(s)", len(alerts))


async def _process_alert(
    bot: Bot, alert_id: int, chat_id: int, api: ScraperAPI, bot_data: dict
) -> None:
    """Busca matches para um alerta, envia carrossel e marca como notificados."""
    try:
        matches_resp = await api.get_matches(alert_id)
    except Exception:
        logger.exception("Polling: falha ao buscar matches do alerta %s", alert_id)
        return

    matches = matches_resp.matches
    if not matches:
        return

    logger.info("Polling: alerta %s tem %s match(es) novo(s)", alert_id, len(matches))

    try:
        await send_carousel(
            bot,
            chat_id,
            matches,
            f"{alert_id}n",  # prefixo 'n' para não conflitar com seed inicial
            bot_data,
        )
    except Exception:
        logger.exception("Polling: falha ao enviar carrossel para alerta %s", alert_id)
        return

    try:
        listing_ids = [m.list_id for m in matches]
        await api.mark_notified(alert_id, listing_ids)
        logger.info(
            "Polling: alerta %s — %s listings marcados como notificados",
            alert_id,
            len(listing_ids),
        )
    except Exception:
        logger.exception("Polling: falha ao marcar notificados para alerta %s", alert_id)