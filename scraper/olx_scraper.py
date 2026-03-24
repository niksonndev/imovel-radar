"""
SCRAPER = cliente HTTP que fala com o OLX via cloudscraper.

- build_search_url: monta a URL de listagem (Maceió + filtros).
- OLXScraper: faz requests via cloudscraper (bypass Cloudflare nativo),
  parseia com parser.py.
"""
from __future__ import annotations

import asyncio
import logging
import random
import re
from typing import Any
from urllib.parse import urlencode

import cloudscraper

import config
from scraper.parser import parse_listing_page, parse_search_page

logger = logging.getLogger(__name__)

BASE = "https://www.olx.com.br"
MACEIO_PATH = "estado-al/alagoas/maceio"


class FetchError(Exception):
    """Erro HTTP retornado pelo servidor."""

    def __init__(self, status_code: int, url: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(f"HTTP {status_code} para {url}")


def build_search_url(filters: dict[str, Any], page: int = 1) -> str:
    """
    filters vêm do alerta no banco (JSON).
    Monta path tipo /imoveis/venda/apartamentos/estado-al/alagoas/maceio?ps=min&pe=max
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
    if pmin:
        params["ps"] = str(int(pmin))
    if pmax:
        params["pe"] = str(int(pmax))
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
        self._scraper = cloudscraper.create_scraper()
        self._cycle_headers: dict[str, str] | None = None

    async def close(self) -> None:
        self._scraper.close()

    async def _delay(self) -> None:
        await asyncio.sleep(random.uniform(config.SCRAPER_DELAY_MIN, config.SCRAPER_DELAY_MAX))

    def _build_headers(self) -> dict[str, str]:
        user_agents = config.USER_AGENTS or [
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        ]
        user_agent = random.choice(user_agents)
        return {
            "User-Agent": user_agent,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "max-age=0",
            "Pragma": "no-cache",
            "Referer": "https://www.olx.com.br/",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Connection": "keep-alive",
        }

    def _sync_get(self, url: str, headers: dict[str, str]) -> tuple[int, str]:
        """GET síncrono via cloudscraper (roda em thread separada)."""
        r = self._scraper.get(
            url,
            timeout=90,
            headers=headers,
        )
        return r.status_code, r.text

    async def fetch(self, url: str, headers: dict[str, str] | None = None) -> str:
        await self._delay()
        req_headers = headers or self._cycle_headers or self._build_headers()
        status_code, text = await asyncio.to_thread(self._sync_get, url, req_headers)
        if status_code >= 400:
            raise FetchError(status_code, url)
        return text

    async def search_listings(
        self, filters: dict[str, Any], max_pages: int | None = 15
    ) -> list[dict]:
        """
        Várias páginas de resultados; dict[olx_id] evita duplicata.
        Depois filtra em Python o que a URL do OLX não filtrou (quartos, m², bairro no texto).
        """
        all_ads: dict[str, dict] = {}
        # Sticky fingerprint por ciclo de busca/paginação.
        self._cycle_headers = self._build_headers()
        try:
            page = 1
            while True:
                if max_pages is not None and page > max_pages:
                    break
                url = build_search_url(filters, page)
                try:
                    html = await self.fetch(url)
                except Exception as e:
                    logger.exception("Erro ao buscar %s: %s", url, e)
                    break
                ads = parse_search_page(html)
                logger.info("Página %s: %s anúncios brutos", page, len(ads))
                if not ads:
                    break
                new_in_page = 0
                for ad in ads:
                    oid = ad["olx_id"]
                    if oid not in all_ads:
                        new_in_page += 1
                    all_ads[oid] = ad
                # Se a página não trouxe IDs novos, consideramos fim da listagem.
                if new_in_page == 0:
                    break
                page += 1
        finally:
            self._cycle_headers = None
        out = list(all_ads.values())
        out = self._apply_local_filters(out, filters)
        logger.info("Total bruto: %s | Após filtro: %s", len(all_ads), len(out))
        return out

    async def search_all_rent_maceio(self) -> list[dict]:
        """
        Coleta completa de aluguel em Maceió.
        Percorre todas as páginas até não haver mais anúncios novos.
        """
        return await self.search_listings(
            {"transaction": "rent", "property_type": "all"},
            max_pages=None,
        )

    def _apply_local_filters(self, ads: list[dict], filters: dict[str, Any]) -> list[dict]:
        # log temporário
        for ad in ads[:5]:
            logger.info(
                "neighborhood: '%s' | title: '%s'",
                ad.get("neighborhood"),
                (ad.get("title") or "")[:50],
            )
        pv = [ad for ad in ads if "ponta verde" in (ad.get("neighborhood") or "").lower()]
        logger.info(
            "Ponta Verde: %s | Cruz das Almas: %s",
            len(pv),
            len([ad for ad in ads if "cruz" in (ad.get("neighborhood") or "").lower()]),
        )
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
