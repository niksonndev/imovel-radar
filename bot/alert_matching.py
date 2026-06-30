"""
Matching entre alertas e o cache local de anúncios.

Camada de caso-de-uso entre o banco (``database/``) e a UI do bot
(``bot/carousel``, ``bot/create_new_alert``, jobs do scheduler). Ela:

- Lê um alerta pelo id (filtros: preço mín/máx, bairros).
- Consulta ``listings`` aplicando esses filtros.
- Normaliza os campos JSON brutos (``images``) para o formato esperado pelo
  carrossel.
- Orquestra dois fluxos prontos para uso:
  * ``seed_alert_carousel`` — chamado logo após criar um alerta; mostra um
    carrossel com os imóveis que já casam e marca todos como "notificados"
    para não serem reenviados no próximo match-job.
  * ``notify_new_matches_all_alerts`` — iterado pelo scheduler após cada
    ``job_daily``; para cada alerta ativo, envia os listings novos (ainda não
    presentes em ``alert_matches``) e grava-os lá.

``list[dict]`` pronto e renderiza. O estado de navegação é gravado em
``app.bot_data`` para funcionar também fora do contexto de um update
(ex.: notificações do scheduler).
"""

from __future__ import annotations

import json
import logging
import sqlite3

from telegram.error import TelegramError
from telegram.ext import Application

from models import Listing

from bot.carousel import send_carousel
from bot.ui import keyboards, menus
from database import (
    get_connection,
    get_alert_by_id,
    get_filtered_listings,
    mark_listings_notified,
)
from hydrator import hydrate_listing

logger = logging.getLogger(__name__)


def find_matches_for_alert(
    conn: sqlite3.Connection,
    alert_id: int,
) -> list[Listing]:

    alert = get_alert_by_id(conn, alert_id)

    neighbourhoods = json.loads(alert["neighbourhoods"])

    filtered_listings = get_filtered_listings(
        conn,
        alert_id,
        alert["min_price"],
        alert["max_price"],
        neighbourhoods,
    )

    return filtered_listings


async def seed_alert_carousel(
    app: Application,
    alert_id: int,
    tg_id: int,
) -> None:
    """Envia carousel com matches atuais após criação do alerta.

    Grava os matches em alert_matches para que notificações futuras
    enviem apenas listings novos.
    """
    bot = app.bot
    conn = get_connection()

    try:
        matches = find_matches_for_alert(conn, alert_id)
        if not matches:
            await bot.send_message(
                chat_id=tg_id,
                text=menus.seed_nenhum_imovel(),
                reply_markup=keyboards.main_menu_keyboard(),
            )
            return

        hydrated = [hydrate_listing(match) for match in matches]

        await send_carousel(bot, tg_id, hydrated, str(alert_id), app.bot_data)
        await bot.send_message(
            chat_id=tg_id,
            text=menus.seed_alert_created(),
            reply_markup=keyboards.main_menu_keyboard(),
        )

        mark_listings_notified(conn, alert_id, [match["listId"] for match in matches])
        conn.commit()

    except Exception:
        conn.rollback()
        logger.exception("Falha no seed do carousel para alerta %s", alert_id)
        try:
            await bot.send_message(chat_id=tg_id, text=menus.seed_sem_cache())
        except TelegramError:
            logger.exception("Falha ao enviar mensagem de erro do seed para %s", tg_id)

    finally:
        conn.close()
