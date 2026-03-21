"""
JOBS = tarefas que rodam no FUNDO de tempo em tempo (APScheduler).

job_alerts: para cada alerta ativo, busca OLX, marca vistos, manda Telegram se for NOVO.
job_watchlist: para cada URL observada, re-baixa página, compara preço ou 404.

app.bot_data = mesmo dicionário que main.py preencheu (session_factory, scraper, ...).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
from telegram.constants import ParseMode

from database import crud
from database.models import User, WatchedListing
from scraper.olx_scraper import build_search_url

logger = logging.getLogger(__name__)


def _fmt_money(v: float | None) -> str:
    if v is None:
        return "—"
    return f"R$ {v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


async def job_alerts(app) -> None:
    session_factory = app.bot_data["session_factory"]
    scraper = app.bot_data["scraper"]
    bot: Bot = app.bot
    async with session_factory() as session:
        alerts = await crud.active_alerts(session)
    for alert in alerts:
        try:
            async with session_factory() as session:
                user = await session.get(User, alert.user_id)
                if not user:
                    continue
                tg_id = user.telegram_id
            listings = await scraper.search_listings(alert.filters or {}, max_pages=6)
            async with session_factory() as session:
                seed_only = alert.last_checked is None
                for ad in listings:
                    oid = ad.get("olx_id")
                    if not oid:
                        continue
                    is_new = await crud.mark_seen(session, alert.id, oid)
                    if seed_only or not is_new:
                        continue
                    title = ad.get("title") or "Imóvel"
                    price = _fmt_money(ad.get("price"))
                    area = ad.get("area_m2")
                    bed = ad.get("bedrooms")
                    nb = ad.get("neighborhood") or "—"
                    url = ad.get("url") or ""
                    area_s = f"{area:g}m²" if area else "—"
                    bed_s = f"{bed} quartos" if bed is not None else "—"
                    text = (
                        f"🏠 *Novo imóvel encontrado!* — Alerta: _{alert.name}_\n\n"
                        f"📍 {title}\n"
                        f"💰 {price}\n"
                        f"📐 {area_s} | 🛏 {bed_s}\n"
                        f"📌 {nb}\n"
                        f"🔗 [Ver anúncio]({url})"
                    )
                    try:
                        await bot.send_message(
                            chat_id=tg_id,
                            text=text,
                            parse_mode=ParseMode.MARKDOWN,
                            disable_web_page_preview=False,
                        )
                        thumb = ad.get("thumbnail")
                        if thumb and thumb.startswith("http"):
                            try:
                                await bot.send_photo(chat_id=tg_id, photo=thumb, caption=title[:200])
                            except Exception:
                                pass
                    except Exception as e:
                        logger.warning("Falha ao notificar %s: %s", tg_id, e)

                if seed_only:
                    count = len(listings)
                    search_url = build_search_url(alert.filters or {}, page=1)
                    seed_text = (
                        f"Alerta {alert.name} ativado! "
                        f"Encontrei {count} imóveis que já correspondem aos seus critérios.\n"
                        f"🔗 [Ver resultados no OLX]({search_url})\n\n"
                        f"A partir de agora, verifico essa busca e vou te avisar "
                        f"quando aparecer algum anúncio novo."
                    )
                    logger.info(
                        "seed_only: enviando resumo do alerta %s (%d imóveis) para tg_id=%s",
                        alert.id, count, tg_id,
                    )
                    try:
                        await bot.send_message(
                            chat_id=tg_id,
                            text=seed_text,
                            parse_mode=ParseMode.MARKDOWN,
                            disable_web_page_preview=True,
                        )
                        logger.info(
                            "seed_only: mensagem de resumo enviada com sucesso para tg_id=%s",
                            tg_id,
                        )
                    except Exception as e:
                        logger.exception(
                            "seed_only: falha ao enviar resumo para tg_id=%s: %s", tg_id, e,
                        )

                await crud.update_alert_last_checked(session, alert.id)
        except Exception as e:
            logger.exception("Alerta %s: %s", alert.id, e)
    app.bot_data["next_alert_run"] = datetime.utcnow() + timedelta(
        minutes=app.bot_data.get("alert_min", 30)
    )


async def job_watchlist(app) -> None:
    session_factory = app.bot_data["session_factory"]
    scraper = app.bot_data["scraper"]
    bot: Bot = app.bot
    async with session_factory() as session:
        watched = await crud.all_active_watched(session)
    for w in watched:
        try:
            info = await scraper.fetch_listing(w.url)
        except Exception as e:
            logger.warning("Watch %s: %s", w.id, e)
            continue
        async with session_factory() as session:
            w2 = await session.get(WatchedListing, w.id)
            if not w2 or not w2.is_active:
                continue
            if info.get("removed") or info.get("not_found"):
                if not w2.removed_notified:
                    user = await session.get(User, w2.user_id)
                    if user:
                        try:
                            await bot.send_message(
                                chat_id=user.telegram_id,
                                text=(
                                    "📴 *Anúncio removido ou indisponível* — Watchlist\n\n"
                                    f"{w2.title or 'Anúncio'}\n"
                                    f"🔗 [Link]({w2.url})"
                                ),
                                parse_mode=ParseMode.MARKDOWN,
                            )
                        except Exception as e:
                            logger.warning(e)
                    await crud.mark_watched_removed(session, w2)
                continue
            new_p = info.get("price")
            old_p = w2.current_price
            if new_p is not None and old_p is not None and new_p != old_p and old_p > 0:
                pct = (new_p - old_p) / old_p * 100
                sign = "+" if pct > 0 else ""
                user = await session.get(User, w2.user_id)
                if user:
                    try:
                        await bot.send_message(
                            chat_id=user.telegram_id,
                            text=(
                                f"⚠️ *Mudança de preço detectada!* — Watchlist\n\n"
                                f"📍 {w2.title or 'Anúncio'}\n"
                                f"💰 ~{_fmt_money(old_p)}~ → *{_fmt_money(new_p)}* "
                                f"({sign}{pct:.1f}%)\n"
                                f"🔗 [Ver anúncio]({w2.url})"
                            ),
                            parse_mode=ParseMode.MARKDOWN,
                        )
                    except Exception as e:
                        logger.warning(e)
            await crud.update_watched_price(
                session,
                w2,
                new_p if new_p is not None else w2.current_price,
                {
                    "price": new_p,
                    "at": datetime.utcnow().isoformat(),
                },
            )
    app.bot_data["next_watch_run"] = datetime.utcnow() + timedelta(
        hours=app.bot_data.get("watch_hours", 6)
    )


def register_jobs(scheduler: AsyncIOScheduler, application) -> None:
    """Agenda dois intervalos: alertas (minutos) e watchlist (horas)."""
    am = application.bot_data.get("alert_min", 30)
    wh = application.bot_data.get("watch_hours", 6)

    async def run_alerts():
        await job_alerts(application)

    async def run_watch():
        await job_watchlist(application)

    scheduler.add_job(
        run_alerts,
        "interval",
        minutes=am,
        id="alerts",
        replace_existing=True,
    )
    scheduler.add_job(
        run_watch,
        "interval",
        hours=wh,
        id="watchlist",
        replace_existing=True,
    )
    application.bot_data["next_alert_run"] = datetime.utcnow() + timedelta(minutes=am)
    application.bot_data["next_watch_run"] = datetime.utcnow() + timedelta(hours=wh)
    logger.info("Jobs registrados: alertas %s min, watchlist %s h", am, wh)
