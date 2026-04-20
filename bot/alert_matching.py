"""
Matching entre alertas e o cache local de anúncios.

Este módulo é a camada de caso-de-uso entre o banco (``database/``) e a UI
do bot (``bot/carousel``, ``bot/create_new_alert``). Ele:

- Lê um alerta pelo id (filtros: preço mín/máx, bairros).
- Consulta ``listings`` aplicando esses filtros.
- Normaliza os campos JSON brutos (``images``) para o formato esperado pelo
  carrossel.
- Opcionalmente, dispara o envio do carrossel e das mensagens de feedback
  para o usuário (``seed_alert_carousel``).

``carousel.py`` continua sendo apenas camada de apresentação: recebe
``list[dict]`` pronto e renderiza. Se outro fluxo (ex.: scheduler cron)
precisar dos matches, importa ``find_matches_for_alert`` e decide como
apresentá-los.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Sequence

from telegram.error import TelegramError
from telegram.ext import Application

from bot.carousel import send_carousel
from bot.ui import keyboards, menus
from database import (
    get_alert_by_id,
    get_connection,
    get_filtered_listings,
)

logger = logging.getLogger(__name__)

DEFAULT_MUNICIPALITY = "Maceió"


def _parse_images_field(raw: object) -> list[object]:
    """Converte o campo ``images`` (JSON string) em ``list``."""
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except Exception:
            return []
        return parsed if isinstance(parsed, list) else []
    if isinstance(raw, list):
        return raw
    return []


def _parse_neighbourhoods_field(raw: object, alert_id: int) -> list[str]:
    """Converte ``alerts.neighbourhoods`` (JSON) em ``list[str]``."""
    if not raw:
        return []
    if isinstance(raw, list):
        return [n for n in raw if isinstance(n, str)]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except Exception:
            logger.warning(
                "neighbourhoods inválido no alerta %s: %r", alert_id, raw
            )
            return []
        if isinstance(parsed, list):
            return [n for n in parsed if isinstance(n, str)]
    return []


def _row_to_ad(row: sqlite3.Row) -> dict:
    """Normaliza uma linha de ``listings`` no formato esperado pelo carrossel."""
    ad = dict(row)
    ad["images"] = _parse_images_field(ad.get("images"))
    return ad


def get_alert_filters(
    conn: sqlite3.Connection, alert_id: int
) -> dict | None:
    """Lê o alerta e devolve só os filtros relevantes para o matching."""
    row = get_alert_by_id(conn, alert_id)
    if row is None:
        return None
    return {
        "min_price": row["min_price"],
        "max_price": row["max_price"],
        "neighbourhoods": _parse_neighbourhoods_field(
            row["neighbourhoods"], alert_id
        ),
    }


def find_matches_for_alert(
    alert_id: int,
    *,
    municipality: str | None = DEFAULT_MUNICIPALITY,
    limit: int | None = None,
) -> list[dict]:
    """Retorna listings ativos que combinam com os filtros do alerta.

    - Sem ``limit`` por padrão: devolve todos os anúncios que casam.
    - ``municipality`` pode ser desligado com ``None`` para matching global.
    - Se o alerta não existir, devolve ``[]``.
    """
    conn = get_connection()
    try:
        filters = get_alert_filters(conn, alert_id)
        if filters is None:
            logger.warning("Alerta %s não encontrado ao buscar matches.", alert_id)
            return []
        rows = get_filtered_listings(
            conn,
            min_price=filters["min_price"],
            max_price=filters["max_price"],
            neighbourhoods=filters["neighbourhoods"] or None,
            municipality=municipality,
            only_active=True,
            limit=limit,
        )
    finally:
        conn.close()

    return [_row_to_ad(row) for row in rows]


def find_matches(
    *,
    min_price: int | None = None,
    max_price: int | None = None,
    neighbourhoods: Sequence[str] | None = None,
    municipality: str | None = DEFAULT_MUNICIPALITY,
    limit: int | None = None,
) -> list[dict]:
    """Versão sem ``alert_id`` útil para scripts/relatórios ad-hoc."""
    conn = get_connection()
    try:
        rows = get_filtered_listings(
            conn,
            min_price=min_price,
            max_price=max_price,
            neighbourhoods=neighbourhoods,
            municipality=municipality,
            only_active=True,
            limit=limit,
        )
    finally:
        conn.close()
    return [_row_to_ad(row) for row in rows]


async def seed_alert_carousel(
    app: Application,
    alert_id: int,
    tg_id: int,
    user_data: dict[str, object],
) -> None:
    """Após criar um alerta, envia um carrossel com os imóveis que já casam.

    Orquestra matching + apresentação:
    - Busca matches via ``find_matches_for_alert``.
    - Se não houver cache/erro, envia ``menus.seed_sem_cache()``.
    - Se vazio, envia ``menus.seed_nenhum_imovel()``.
    - Caso contrário, envia o carrossel e a confirmação final.
    """
    bot = app.bot

    try:
        matches = find_matches_for_alert(alert_id)
    except Exception:
        logger.exception(
            "Falha ao buscar matches no cache local para alerta %s", alert_id
        )
        try:
            await bot.send_message(chat_id=tg_id, text=menus.seed_sem_cache())
        except TelegramError:
            logger.exception(
                "Falha ao enviar mensagem de erro do seed para %s", tg_id
            )
        return

    if not matches:
        await bot.send_message(
            chat_id=tg_id,
            text=menus.seed_nenhum_imovel(),
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return

    await send_carousel(bot, tg_id, matches, str(alert_id), user_data)
    await bot.send_message(
        chat_id=tg_id,
        text=menus.seed_alert_created(),
        reply_markup=keyboards.main_menu_keyboard(),
    )
