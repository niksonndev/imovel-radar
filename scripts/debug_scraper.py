from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

# `config.py` exige TELEGRAM_BOT_TOKEN ao importar `scraper.olx_scraper`.
# Para este script de debug do scraper, um valor dummy e suficiente.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "debug-token")

import config
from scraper.olx_scraper import extract_listings_from_search_page, fetch
from utils.models import Listing

ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT / "logs"
LOG_FILE = LOGS_DIR / "debug_scraper.log"
PAGE1_NEXT_DATA = LOGS_DIR / "debug_scraper_page1_next_data.json"
PAGE1_LISTINGS = LOGS_DIR / "debug_scraper_page1_listings.json"

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


def _extract_next_data(html: str) -> dict[str, Any]:
    script = BeautifulSoup(html, "lxml").find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        raise SystemExit('Tag <script id="__NEXT_DATA__"> não encontrada ou vazia')
    return json.loads(script.string)


def _count_ads_objects(next_data: dict[str, Any]) -> int:
    ads = next_data["props"]["pageProps"]["ads"]
    if not isinstance(ads, list):
        raise SystemExit("`props.pageProps.ads` não é uma lista")
    return sum(1 for item in ads if isinstance(item, dict))


async def main() -> None:
    setup_logging()

    logger.info("Iniciando debug do scraper OLX")
    logger.info("URL base da coleta: %s", config.MACEIO_RENT_LISTINGS_URL)

    html = await fetch(config.MACEIO_RENT_LISTINGS_URL)
    next_data = _extract_next_data(html)
    _write_json(PAGE1_NEXT_DATA, next_data)
    logger.info("__NEXT_DATA__ da primeira página salvo em %s", PAGE1_NEXT_DATA)
    logger.info(
        "`props.pageProps.ads` contém %s objetos",
        _count_ads_objects(next_data),
    )

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


if __name__ == "__main__":
    asyncio.run(main())
