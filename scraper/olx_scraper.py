"""Cliente HTTP + montagem de URLs OLX Maceió."""
from __future__ import annotations

import asyncio
import logging
import random
import re
from typing import Any
from urllib.parse import urlencode

import httpx

import config
from scraper.parser import parse_listing_page, parse_search_page

logger = logging.getLogger(__name__)

BASE = "https://www.olx.com.br"
MACEIO_PATH = "estado-al/alagoas/maceio"


def build_search_url(filters: dict[str, Any], page: int = 1) -> str:
    """
    filters: property_type, transaction, price_min, price_max, bedrooms_min,
    area_min, area_max, neighborhoods (list)
    """
    ptype = config.PROPERTY_TYPE_SLUGS.get(filters.get("property_type") or "apartment", "apartamentos")
    trans = config.TRANSACTION_SLUGS.get(filters.get("transaction") or "sale", "venda")
    path = f"/imoveis/{trans}/{ptype}/{MACEIO_PATH}"
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
    url = BASE + path
    if params:
        url += "?" + urlencode(params)
    return url


def extract_olx_id_from_url(url: str) -> str | None:
    m = re.search(r"/(\d{8,})(?:\?|$)", url)
    return m.group(1) if m else None


class OLXScraper:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=45.0,
                follow_redirects=True,
                headers={"Accept-Language": "pt-BR,pt;q=0.9"},
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _delay(self) -> None:
        await asyncio.sleep(random.uniform(config.SCRAPER_DELAY_MIN, config.SCRAPER_DELAY_MAX))

    def _ua(self) -> dict[str, str]:
        return {"User-Agent": random.choice(config.USER_AGENTS)}

    async def fetch(self, url: str) -> str:
        await self._delay()
        client = await self._get_client()
        r = await client.get(url, headers=self._ua())
        r.raise_for_status()
        return r.text

    async def search_listings(self, filters: dict[str, Any], max_pages: int = 8) -> list[dict]:
        """Agrega várias páginas; filtra localmente por quartos/área se necessário."""
        all_ads: dict[str, dict] = {}
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
        if not url.startswith("http"):
            url = BASE + url
        try:
            html = await self.fetch(url)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {"removed": True, "not_found": True, "price": None, "title": None}
            raise
        return parse_listing_page(html)
