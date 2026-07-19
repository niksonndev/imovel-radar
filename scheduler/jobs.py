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
from datetime import datetime

from telegram.ext import Application

import config
import scraper
from bot.alert_matching import seed_alert_carousel
from database import get_connection
from database.queries import list_active_alerts_with_chat, upsert_listing

logger = logging.getLogger(__name__)

# Limite para a fase assíncrona (Telegram): evita o job do scheduler ficar pendurado para sempre
# se a rede ou a API travarem; o PTB continua na thread principal com seu próprio loop.
_NOTIFY_TIMEOUT_SECONDS = 600


def _do_full_scrape() -> tuple[bool, int]:
    """Coleta anúncios OLX e persiste no SQLite. Retorna sucesso e total coletado."""
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
        return True, len(listings)
    except Exception:
        logger.exception("Coleta agendada falhou")
        return False, 0


async def _alert_admin_scrape_issue(app: Application, reason: str) -> None:
    """Notifica o admin quando o scrape diário falha ou retorna vazio.

    Nunca propaga exceção — falha de envio aqui não pode derrubar o restante do job.
    """
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    message = f"Alerta operacional do scraper ({timestamp}): {reason}"
    try:
        await app.bot.send_message(chat_id=config.ADMIN_CHAT_ID, text=message)
    except Exception:
        logger.exception("Falha ao enviar alerta operacional do scraper ao admin")


async def _notify_new_matches_all_alerts(app: Application) -> None:
    """Job diário: notifica matches novos para cada alerta ativo."""
    conn = get_connection()
    try:
        alerts = list_active_alerts_with_chat(conn)
    finally:
        conn.close()

    if not alerts:
        logger.info("notify: nenhum alerta ativo")
        return

    for alert in alerts:
        try:
            await seed_alert_carousel(app, alert["id"], alert["chat_id"])
        except Exception:
            logger.exception("notify: falha ao processar alerta %s", alert["id"])
        await asyncio.sleep(2)  # avoid flood of telegram messages

    logger.info("notify: %s alerta(s) processado(s)", len(alerts))


def job_full_scrape() -> None:
    """Wrapper retrocompatível: apenas faz o scrape, sem notificações."""
    _success, _count = _do_full_scrape()


def run_initial_scrape() -> bool:
    """Scrape inicial executado no bootstrap quando o DB ainda não existe.

    Usado em deploys novos (ex.: subida na Oracle) para popular o ``imoveis.db``
    antes do primeiro disparo do cron diário. Não envia notificações — numa base
    recém-criada não há alertas cadastrados, então qualquer notificação seria
    ruído.
    """
    logger.info("Scrape inicial: base recém-criada, populando do zero")
    success, _count = _do_full_scrape()
    return success


def job_daily(app: Application, loop: asyncio.AbstractEventLoop) -> None:
    """Job diário: full scrape + notificação dos novos matches por alerta.

    Roda na thread do ``BackgroundScheduler``. A parte assíncrona (envio via
    Telegram) é despachada no event loop do PTB via ``run_coroutine_threadsafe``
    e aguardada com timeout para garantir ordem de execução e logs corretos.
    """
    success, count = _do_full_scrape()
    if not success:
        logger.warning("job_daily: pulando notificações porque o scrape falhou")
        try:
            fut = asyncio.run_coroutine_threadsafe(
                _alert_admin_scrape_issue(app, "Coleta falhou com exceção — ver logs do scraper"),
                loop,
            )
            fut.result(timeout=_NOTIFY_TIMEOUT_SECONDS)
        except Exception:
            logger.exception("job_daily: falha ao enviar alerta de erro do scrape ao admin")
        return

    if count == 0:
        try:
            fut = asyncio.run_coroutine_threadsafe(
                _alert_admin_scrape_issue(
                    app,
                    "Coleta concluída mas retornou 0 anúncios — possível bloqueio "
                    "ou mudança na OLX",
                ),
                loop,
            )
            fut.result(timeout=_NOTIFY_TIMEOUT_SECONDS)
        except Exception:
            logger.exception("job_daily: falha ao enviar alerta de coleta vazia ao admin")

    try:
        # notify_* é async e precisa do loop do PTB; run_coroutine_threadsafe
        # "ponteia" thread do cron → thread do bot.
        fut = asyncio.run_coroutine_threadsafe(_notify_new_matches_all_alerts(app), loop)
        summary = fut.result(timeout=_NOTIFY_TIMEOUT_SECONDS)
        logger.info("job_daily: notify summary=%s", summary)
    except Exception:
        logger.exception("job_daily: etapa de notificação falhou")
