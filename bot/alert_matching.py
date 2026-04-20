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

``carousel.py`` continua sendo apenas camada de apresentação: recebe
``list[dict]`` pronto e renderiza. O estado de navegação é gravado em
``app.bot_data`` para funcionar também fora do contexto de um update
(ex.: notificações do scheduler).
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from typing import Sequence

from telegram.error import TelegramError
from telegram.ext import Application

from bot.carousel import send_carousel
from bot.ui import keyboards, menus
from database import (
    get_active_alerts_with_chat,
    get_alert_by_id,
    get_connection,
    get_filtered_listings,
    get_unnotified_matches_for_alert,
    mark_listings_notified,
)

logger = logging.getLogger(__name__)

DEFAULT_MUNICIPALITY = "Maceió"
# Pausa curta entre notificações para usuários distintos, para não estourar
# o rate-limit do Bot API (30 msg/s global).
_NOTIFY_USER_GAP_SECONDS = 0.1


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


def _mark_all_notified(alert_id: int, listing_ids: list[int]) -> None:
    """Grava ``alert_matches`` em uma conexão dedicada (isolada do matching)."""
    if not listing_ids:
        return
    conn = get_connection()
    try:
        mark_listings_notified(conn, alert_id, listing_ids)
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception(
            "Falha ao marcar %s listings como notificados (alerta %s)",
            len(listing_ids),
            alert_id,
        )
    finally:
        conn.close()


async def seed_alert_carousel(
    app: Application,
    alert_id: int,
    tg_id: int,
) -> None:
    """Após criar um alerta, envia um carrossel com os imóveis que já casam.

    Também grava TODOS os matches atuais em ``alert_matches`` para que o
    ``notify_new_matches_all_alerts`` do próximo scrape só envie o que for
    novo de verdade.

    Estado do carrossel vai para ``app.bot_data`` para que a navegação
    funcione em qualquer handler/chat.
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

    await send_carousel(bot, tg_id, matches, str(alert_id), app.bot_data)
    await bot.send_message(
        chat_id=tg_id,
        text=menus.seed_alert_created(),
        reply_markup=keyboards.main_menu_keyboard(),
    )

    _mark_all_notified(
        alert_id,
        [int(ad["listId"]) for ad in matches if ad.get("listId") is not None],
    )


# ────────────────────── notificação recorrente (scheduler) ──────────────────────


async def _notify_one_alert(app: Application, alert_row: sqlite3.Row) -> int:
    """Envia novas casadas para um alerta. Retorna quantos foram notificados."""
    alert_id = int(alert_row["id"])
    chat_id = int(alert_row["chat_id"])
    alert_name = alert_row["alert_name"] or f"alerta #{alert_id}"
    nbs = _parse_neighbourhoods_field(alert_row["neighbourhoods"], alert_id)

    conn = get_connection()
    try:
        rows = get_unnotified_matches_for_alert(
            conn,
            alert_id,
            min_price=alert_row["min_price"],
            max_price=alert_row["max_price"],
            neighbourhoods=nbs or None,
            municipality=DEFAULT_MUNICIPALITY,
        )
    finally:
        conn.close()

    if not rows:
        return 0

    ads = [_row_to_ad(r) for r in rows]
    listing_ids = [int(ad["listId"]) for ad in ads if ad.get("listId") is not None]

    try:
        await app.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🔔 {len(ads)} novo(s) imóvel(is) para o alerta "
                f"*{alert_name}*"
            ),
            parse_mode="Markdown",
        )
        # carousel_id com sufixo 'n' para não colidir com o seed (id=str(alert_id))
        # nem com futuros carrosséis diferentes do mesmo alerta.
        await send_carousel(
            app.bot, chat_id, ads, f"{alert_id}n", app.bot_data
        )
    except TelegramError:
        logger.exception(
            "Falha ao enviar notificação do alerta %s para chat %s",
            alert_id,
            chat_id,
        )
        # Mesmo que o envio falhe, NÃO marcamos como notificado — assim a
        # próxima rodada tenta de novo.
        return 0

    _mark_all_notified(alert_id, listing_ids)
    return len(ads)


async def notify_new_matches_all_alerts(app: Application) -> dict:
    """Para cada alerta ativo, notifica imóveis novos e grava em ``alert_matches``.

    Retorna um resumo ``{"alerts": N, "notified": M}`` útil para logs do job.
    """
    conn = get_connection()
    try:
        alerts = get_active_alerts_with_chat(conn)
    finally:
        conn.close()

    if not alerts:
        logger.info("notify: nenhum alerta ativo")
        return {"alerts": 0, "notified": 0}

    total_notified = 0
    for a in alerts:
        try:
            n = await _notify_one_alert(app, a)
            total_notified += n
            if n > 0:
                logger.info(
                    "notify: alerta %s (chat %s) — %s novo(s)",
                    a["id"],
                    a["chat_id"],
                    n,
                )
        except Exception:
            logger.exception(
                "Falha ao notificar alerta %s", a["id"] if "id" in a.keys() else "?"
            )
        await asyncio.sleep(_NOTIFY_USER_GAP_SECONDS)

    logger.info(
        "notify: %s alerta(s) processado(s), %s notificação(ões) enviada(s)",
        len(alerts),
        total_notified,
    )
    return {"alerts": len(alerts), "notified": total_notified}
