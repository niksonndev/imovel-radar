"""
SCRAPER = navegador headless que acessa o site do OLX via Playwright.

- build_search_url: monta a URL de listagem (Maceió + filtros).
- OLXScraper: renderiza páginas com Chromium + stealth, parseia com parser.py.
"""
from __future__ import annotations

import asyncio
import logging
import random
import re
from typing import Any
from urllib.parse import urlencode

from playwright.async_api import async_playwright, Browser, Playwright
from playwright_stealth import Stealth

import config
from scraper.parser import parse_listing_page, parse_search_page

logger = logging.getLogger(__name__)

BASE = "https://www.olx.com.br"
MACEIO_PATH = "estado-al/alagoas/maceio"


class FetchError(Exception):
    """Erro HTTP retornado pelo servidor ao navegar com Playwright."""

    def __init__(self, status_code: int, url: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(f"HTTP {status_code} para {url}")


def build_search_url(filters: dict[str, Any], page: int = 1) -> str:
    """
    filters vêm do alerta no banco (JSON).
    Monta path tipo /imoveis/venda/apartamentos/estado-al/alagoas/maceio?pe=min-max&q=bairros
    Se property_type for "all" (ou None no slug), omite o segmento de tipo,
    gerando /imoveis/venda/estado-al/alagoas/maceio  (todos os tipos).
    """
    ptype_slug = config.PROPERTY_TYPE_SLUGS.get(
        filters.get("property_type") or "all"
    )
    trans = config.TRANSACTION_SLUGS.get(filters.get("transaction") or "sale", "venda")
    if ptype_slug:
        path = f"/imoveis/{trans}/{ptype_slug}/{MACEIO_PATH}"
    else:
        path = f"/imoveis/{trans}/{MACEIO_PATH}"
    params: dict[str, str] = {}
    if page > 1:
        params["o"] = str(page)
    pmin = filters.get("price_min")
    pmax = filters.get("price_max")
    if pmin is not None or pmax is not None:
        a = int(pmin or 0)
        b = int(pmax or 999_999_999)
        params["pe"] = f"{a}-{b}"
    q_parts = filters.get("neighborhoods") or []
    if q_parts:
        params["q"] = " ".join(q_parts)
    sp = filters.get("sp")
    if sp is not None:
        params["sp"] = str(sp)
    url = BASE + path
    if params:
        url += "?" + urlencode(params)
    return url


def extract_olx_id_from_url(url: str) -> str | None:
    """ID numérico longo que aparece na URL do anúncio."""
    m = re.search(r"/(\d{8,})(?:\?|$)", url)
    return m.group(1) if m else None


class OLXScraper:
    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def _ensure_browser(self) -> Browser:
        if self._browser is None or not self._browser.is_connected():
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
        return self._browser

    async def _close_browser(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def close(self) -> None:
        await self._close_browser()

    async def _delay(self) -> None:
        await asyncio.sleep(random.uniform(config.SCRAPER_DELAY_MIN, config.SCRAPER_DELAY_MAX))

    async def fetch(self, url: str) -> str:
        await self._delay()
        browser = await self._ensure_browser()
        page = await browser.new_page()
        try:
            await Stealth().apply_stealth_async(page)
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            if resp is not None and resp.status >= 400:
                raise FetchError(resp.status, url)
            return await page.content()
        finally:
            await page.close()

    async def search_listings(self, filters: dict[str, Any], max_pages: int = 8) -> list[dict]:
        """
        Várias páginas de resultados; dict[olx_id] evita duplicata.
        Depois filtra em Python o que a URL do OLX não filtrou (quartos, m², bairro no texto).
        """
        all_ads: dict[str, dict] = {}
        try:
            for page in range(1, max_pages + 1):
                url = build_search_url(filters, page)
                try:
                    html = await self.fetch(url)
                except Exception as e:
                    logger.exception("Erro ao buscar %s: %s", url, e)
                    break
                ads = parse_search_page(html)
                if not ads:
                    break
                for ad in ads:
                    all_ads[ad["olx_id"]] = ad
                if len(ads) < 20:
                    break
        finally:
            await self._close_browser()
        out = list(all_ads.values())
        out = self._apply_local_filters(out, filters)
        return out

    def _apply_local_filters(self, ads: list[dict], filters: dict[str, Any]) -> list[dict]:
        bmin = filters.get("bedrooms_min")
        amin = filters.get("area_min")
        amax = filters.get("area_max")
        neighborhoods = [n.lower() for n in (filters.get("neighborhoods") or [])]
        result = []
        for ad in ads:
            if bmin is not None and ad.get("bedrooms") is not None:
                if ad["bedrooms"] < bmin:
                    continue
            if amin is not None and ad.get("area_m2") is not None:
                if ad["area_m2"] < amin:
                    continue
            if amax is not None and ad.get("area_m2") is not None:
                if ad["area_m2"] > amax:
                    continue
            if neighborhoods:
                blob = (ad.get("title") or "") + " " + (ad.get("neighborhood") or "")
                blob = blob.lower()
                if not any(n in blob for n in neighborhoods):
                    continue
            result.append(ad)
        return result

    async def fetch_listing(self, url: str) -> dict[str, Any]:
        """Uma página de anúncio só (watchlist)."""
        if not url.startswith("http"):
            url = BASE + url
        try:
            html = await self.fetch(url)
        except FetchError as e:
            if e.status_code == 404:
                return {"removed": True, "not_found": True, "price": None, "title": None}
            raise
        finally:
            await self._close_browser()
        return parse_listing_page(html)
