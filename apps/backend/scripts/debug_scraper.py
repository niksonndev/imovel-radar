"""
Debug helpers para o scraper OLX.

Uso:
    python -m scripts.debug_scraper extract-page
    python -m scripts.debug_scraper search-all
    python -m scripts.debug_scraper dump-rsc
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

# `config.py` exige TELEGRAM_BOT_TOKEN ao importar `scraper.olx_scraper`.
# Para este script de debug do scraper, um valor dummy e suficiente.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "debug-token")

import config
from models import Listing
from scraper.olx_scraper import (
    _extract_ads_container_from_rsc,
    _extract_rsc_payload,
    extract_listings_from_search_page,
    fetch,
    search_all_rent_maceio,
)

ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT / "logs"
LOG_FILE = LOGS_DIR / "debug_scraper.log"
PAGE1_ADS_PAYLOAD = LOGS_DIR / "debug_scraper_page1_ads_payload.json"
PAGE1_LISTINGS = LOGS_DIR / "debug_scraper_page1_listings.json"
SEARCH_ALL_LISTINGS = LOGS_DIR / "debug_scraper_search_all_listings.json"
DEBUG_LAST_RESPONSE = ROOT / "debug_last_response.html"
DEBUG_RSC_PAYLOAD = ROOT / "debug_rsc_payload.txt"

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


def _listing_debug_view(listing: Listing) -> dict[str, Any]:
    return {
        **listing,
        "properties": json.loads(listing["properties"]),
        "images": json.loads(listing["images"]),
    }


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


async def debug_extract_listings_from_search_page() -> None:
    logger.info("Iniciando debug de extract_listings_from_search_page")
    logger.info("URL base da coleta: %s", config.MACEIO_RENT_LISTINGS_URL)

    html = await fetch(config.MACEIO_RENT_LISTINGS_URL)
    ads_container = _extract_ads_container_from_rsc(html)
    ads = ads_container["ads"]
    _write_json(PAGE1_ADS_PAYLOAD, ads)
    logger.info("Anúncios extraídos do RSC salvos em %s", PAGE1_ADS_PAYLOAD)
    logger.info("Array `ads` extraído do RSC contém %s objetos", len(ads))

    page1_listings = extract_listings_from_search_page(html)
    _write_json(
        PAGE1_LISTINGS,
        [_listing_debug_view(listing) for listing in page1_listings],
    )
    logger.info(
        "Primeira página parseada: %s anúncios salvos em %s",
        len(page1_listings),
        PAGE1_LISTINGS,
    )


async def debug_search_all_rent_maceio() -> None:
    logger.info("Iniciando debug de search_all_rent_maceio")
    logger.info("URL base da coleta: %s", config.MACEIO_RENT_LISTINGS_URL)

    listings = await search_all_rent_maceio()
    _write_json(
        SEARCH_ALL_LISTINGS,
        [_listing_debug_view(listing) for listing in listings],
    )
    logger.info(
        "Coleta paginada concluída: %s anúncios salvos em %s",
        len(listings),
        SEARCH_ALL_LISTINGS,
    )


def debug_dump_rsc() -> None:
    html = DEBUG_LAST_RESPONSE.read_text(encoding="utf-8")
    payload = _extract_rsc_payload(html)
    DEBUG_RSC_PAYLOAD.write_text(payload, encoding="utf-8")
    logger.info(
        '"ads" encontrado: %s, tamanho: %s',
        '"ads":[' in payload,
        len(payload),
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Debug do scraper OLX")
    parser.add_argument(
        "command",
        choices=("extract-page", "search-all", "dump-rsc"),
        help=(
            "`extract-page` testa extract_listings_from_search_page; "
            "`search-all` testa search_all_rent_maceio; "
            "`dump-rsc` extrai o payload RSC salvo"
        ),
    )
    return parser


async def main() -> None:
    setup_logging()
    args = _build_arg_parser().parse_args()

    if args.command == "extract-page":
        await debug_extract_listings_from_search_page()
        return

    if args.command == "search-all":
        await debug_search_all_rent_maceio()
        return

    if args.command == "dump-rsc":
        debug_dump_rsc()
        return

    raise SystemExit(f"Comando não suportado: {args.command}")


if __name__ == "__main__":
    asyncio.run(main())
