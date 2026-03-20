"""
SCRAPER = cliente HTTP que fala com o OLX via ScrapingBee.

- build_search_url: monta a URL de listagem (Maceió + filtros).
- OLXScraper: faz requests via ScrapingBee (proxy com browser real),
  parseia com parser.py.
"""
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
SCRAPINGBEE_ENDPOINT = "https://app.scrapingbee.com/api/v1/"


class FetchError(Exception):
    """Erro HTTP retornado pelo servidor (via ScrapingBee ou direto)."""

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
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=90.0,
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

    async def fetch(self, url: str) -> str:
        await self._delay()
        client = await self._get_client()
        params = {
            "api_key": config.SCRAPINGBEE_API_KEY,
            "url": url,
            "render_js": "true",
        }
        r = await client.get(SCRAPINGBEE_ENDPOINT, params=params)
        if r.status_code >= 400:
            raise FetchError(r.status_code, url)
        return r.text

    async def search_listings(self, filters: dict[str, Any], max_pages: int = 8) -> list[dict]:
        """
        Várias páginas de resultados; dict[olx_id] evita duplicata.
        Depois filtra em Python o que a URL do OLX não filtrou (quartos, m², bairro no texto).
        """
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
        """Uma página de anúncio só (watchlist)."""
        if not url.startswith("http"):
            url = BASE + url
        try:
            html = await self.fetch(url)
        except FetchError as e:
            if e.status_code == 404:
                return {"removed": True, "not_found": True, "price": None, "title": None}
            raise
        return parse_listing_page(html)
