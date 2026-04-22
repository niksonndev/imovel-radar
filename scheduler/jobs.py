"""
Jobs agendados do APScheduler.

``job_daily`` é o job composto que roda 1x/dia: faz o full scrape e,
em seguida, notifica os alertas com os imóveis novos.

``_do_full_scrape`` e ``notify_new_matches_all_alerts`` (de
``bot.alert_matching``) podem ser chamados independentemente — útil para
execução manual / ad-hoc via REPL ou testes.
"""

from __future__ import annotations

import asyncio
import logging

from telegram.ext import Application

import scraper
from bot.alert_matching import notify_new_matches_all_alerts
from database import get_connection
from database.queries import upsert_listing

logger = logging.getLogger(__name__)

# Limite para a fase assíncrona (Telegram): evita o job do scheduler ficar pendurado para sempre
# se a rede ou a API travarem; o PTB continua na thread principal com seu próprio loop.
_NOTIFY_TIMEOUT_SECONDS = 600


def _do_full_scrape() -> bool:
    """Coleta anúncios OLX e persiste no SQLite. Retorna ``True`` se OK."""
    try:
        logger.info("Coleta agendada: início")
        listings = scraper.coletar()
        conn = get_connection()
        try:
            # Um único commit no fim: ou grava o lote inteiro ou nada (evita DB “pela metade”).
            for listing in listings:
                upsert_listing(conn, listing)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        logger.info("Coleta agendada: fim (%s anúncios)", len(listings))
        return True
    except Exception:
        logger.exception("Coleta agendada falhou")
        return False


def job_full_scrape() -> None:
    """Wrapper retrocompatível: apenas faz o scrape, sem notificações."""
    _do_full_scrape()


def run_initial_scrape() -> bool:
    """Scrape inicial executado no bootstrap quando o DB ainda não existe.

    Usado em deploys novos (ex.: subida na Oracle) para popular o ``imoveis.db``
    antes do primeiro disparo do cron diário. Não envia notificações — numa base
    recém-criada não há alertas cadastrados, então qualquer notificação seria
    ruído.
    """
    logger.info("Scrape inicial: base recém-criada, populando do zero")
    return _do_full_scrape()


def job_daily(app: Application, loop: asyncio.AbstractEventLoop) -> None:
    """Job diário: full scrape + notificação dos novos matches por alerta.

    Roda na thread do ``BackgroundScheduler``. A parte assíncrona (envio via
    Telegram) é despachada no event loop do PTB via ``run_coroutine_threadsafe``
    e aguardada com timeout para garantir ordem de execução e logs corretos.
    """
    if not _do_full_scrape():
        logger.warning("job_daily: pulando notificações porque o scrape falhou")
        return

    try:
        # notify_* é async e precisa do loop do PTB; run_coroutine_threadsafe “ponteia” thread do cron → thread do bot.
        fut = asyncio.run_coroutine_threadsafe(
            notify_new_matches_all_alerts(app), loop
        )
        summary = fut.result(timeout=_NOTIFY_TIMEOUT_SECONDS)
        logger.info("job_daily: notify summary=%s", summary)
    except Exception:
        logger.exception("job_daily: etapa de notificação falhou")
