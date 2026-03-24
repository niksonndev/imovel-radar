"""
JOBS = tarefas que rodam no FUNDO de tempo em tempo (APScheduler).

job_alerts: para cada alerta ativo, busca OLX, marca vistos, manda Telegram se for NOVO.
job_watchlist: para cada URL observada, re-baixa página, compara preço ou 404.

app.bot_data = mesmo dicionário que main.py preencheu (session_factory, scraper, ...).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
from telegram.constants import ParseMode

from bot.carousel import send_carousel, MAX_NOTIF_CAROUSEL
from database import crud
from database.models import User, WatchedListing
from db.cache import deactivate_missing, upsert_listing
from db.parsers import parse_listing
from scraper.olx_scraper import fetch_listing, search_all_rent_maceio

logger = logging.getLogger(__name__)
MACEIO_TZ = ZoneInfo("America/Maceio")


def _next_maceio_3am() -> datetime:
    now = datetime.now(MACEIO_TZ)
    target = now.replace(hour=3, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


def _fmt_money(v: float | None) -> str:
    if v is None:
        return "—"
    return f"R$ {v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _filter_listings_inhouse(listings: list[dict], filters: dict) -> list[dict]:
    pmin = filters.get("price_min")
    pmax = filters.get("price_max")
    bmin = filters.get("bedrooms_min")
    amin = filters.get("area_min")
    amax = filters.get("area_max")
    neighborhoods = [n.lower() for n in (filters.get("neighborhoods") or [])]
    out: list[dict] = []
    for ad in listings:
        if pmin is not None and ad.get("price") is not None and ad["price"] < pmin:
            continue
        if pmax is not None and ad.get("price") is not None and ad["price"] > pmax:
            continue
        if bmin is not None and ad.get("bedrooms") is not None and ad["bedrooms"] < bmin:
            continue
        if amin is not None and ad.get("area_m2") is not None and ad["area_m2"] < amin:
            continue
        if amax is not None and ad.get("area_m2") is not None and ad["area_m2"] > amax:
            continue
        if neighborhoods:
            blob = ((ad.get("title") or "") + " " + (ad.get("neighborhood") or "")).lower()
            if not any(n in blob for n in neighborhoods):
                continue
        out.append(ad)
    return out


async def job_alerts(app) -> None:
    session_factory = app.bot_data["session_factory"]
    bot: Bot = app.bot
    async with session_factory() as session:
        alerts = await crud.active_alerts(session)
    try:
        full_listings = await search_all_rent_maceio()
    except Exception as e:
        logger.exception("Falha no scrape global de aluguel Maceió: %s", e)
        app.bot_data["next_alert_run"] = _next_maceio_3am()
        return

    cycle_seen_ids: set[int] = set()
    cycle_cache_stats = {"created": 0, "updated": 0, "unchanged": 0}
    for raw in full_listings:
        try:
            parsed = parse_listing(raw)
            status = upsert_listing(parsed)
            cycle_cache_stats[status] += 1
            cycle_seen_ids.add(parsed["list_id"])
        except Exception as e:
            logger.warning("Falha ao atualizar cache do anuncio: %s", e)

    for alert in alerts:
        try:
            async with session_factory() as session:
                user = await session.get(User, alert.user_id)
                if not user:
                    continue
                tg_id = user.telegram_id
            if (alert.filters or {}).get("transaction") == "sale":
                listings = []
            else:
                listings = _filter_listings_inhouse(full_listings, alert.filters or {})

            async with session_factory() as session:
                seed_only = alert.last_checked is None
                new_ads: list[dict] = []
                for ad in listings:
                    oid = ad.get("olx_id")
                    if not oid:
                        continue
                    is_new = await crud.mark_seen(session, alert.id, oid)
                    if is_new and not seed_only:
                        new_ads.append(ad)

                if not seed_only and new_ads:
                    count = len(new_ads)
                    plural = "imóvel novo" if count == 1 else "imóveis novos"
                    try:
                        await bot.send_message(
                            chat_id=tg_id,
                            text=(
                                f"🔔 Alerta *{alert.name}* — "
                                f"encontrei *{count}* {plural}!"
                            ),
                            parse_mode=ParseMode.MARKDOWN,
                        )
                    except Exception as e:
                        logger.warning("Falha ao notificar %s: %s", tg_id, e)

                    carousel_ads = new_ads[:MAX_NOTIF_CAROUSEL]
                    transaction = (alert.filters or {}).get("transaction", "sale")
                    carousel_id = f"{alert.id}_notif"
                    user_data = app.user_data[tg_id]
                    try:
                        await send_carousel(
                            bot, tg_id, carousel_ads, transaction,
                            carousel_id, user_data,
                        )
                    except Exception as e:
                        logger.warning("Falha ao enviar carrossel %s: %s", tg_id, e)

                if seed_only:
                    count = len(listings)
                    f = alert.filters or {}
                    nh = f.get("neighborhoods") or []
                    bairros = ", ".join(nh) if nh else "Maceió"
                    preco = f"{_fmt_money(f.get('price_min'))} - {_fmt_money(f.get('price_max'))}"
                    seed_text = (
                        f"✅ Alerta *{alert.name}* ativado!\n"
                        f"Encontrei *{count}* imóveis em *{bairros}* com preço entre *{preco}*.\n\n"
                        f"A partir de agora, verifico essa busca e vou te avisar quando aparecer "
                        f"algum anúncio novo. 🔔"
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
    deactivated = deactivate_missing(list(cycle_seen_ids))
    logger.info(
        "Cache do ciclo: %s | desativados=%s",
        cycle_cache_stats,
        deactivated,
    )
    app.bot_data["next_alert_run"] = _next_maceio_3am()


async def job_watchlist(app) -> None:
    session_factory = app.bot_data["session_factory"]
    bot: Bot = app.bot
    async with session_factory() as session:
        watched = await crud.all_active_watched(session)
    for w in watched:
        try:
            info = await fetch_listing(w.url)
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
        days=app.bot_data.get("watch_days", 1)
    )


def register_jobs(scheduler: AsyncIOScheduler, application) -> None:
    """Agenda scraping diário 03:00 (Maceió) e watchlist diária."""
    scrape_days = application.bot_data.get("scrape_days", 1)
    watch_days = application.bot_data.get("watch_days", 1)

    async def run_alerts():
        await job_alerts(application)

    async def run_watch():
        await job_watchlist(application)

    scheduler.add_job(
        run_alerts,
        "cron",
        hour=3,
        minute=0,
        timezone=MACEIO_TZ,
        id="alerts",
        replace_existing=True,
    )
    scheduler.add_job(
        run_watch,
        "interval",
        days=watch_days,
        id="watchlist",
        replace_existing=True,
    )
    application.bot_data["next_alert_run"] = _next_maceio_3am()
    application.bot_data["next_watch_run"] = datetime.utcnow() + timedelta(days=watch_days)
    logger.info(
        "Jobs registrados: scraping diario as 03:00 (America/Maceio), watchlist a cada %s dia(s)",
        watch_days,
    )
