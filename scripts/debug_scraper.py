from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

# `config.py` exige TELEGRAM_BOT_TOKEN ao importar `scraper.olx_scraper`.
# Para este script de debug do scraper, um valor dummy é suficiente.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "debug-token")

import config
from scraper.olx_scraper import extract_listings_from_search_page, fetch
from utils.models import Listing

ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT / "logs"
LOG_FILE = LOGS_DIR / "debug_scraper.log"
PAGE1_HTML = LOGS_DIR / "debug_scraper_page1.html"
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


async def main() -> None:
    setup_logging()

    logger.info("Iniciando debug do scraper OLX")
    logger.info("URL base da coleta: %s", config.MACEIO_RENT_LISTINGS_URL)

    html = await fetch(config.MACEIO_RENT_LISTINGS_URL)
    PAGE1_HTML.write_text(html, encoding="utf-8")
    logger.info("HTML da primeira página salvo em %s", PAGE1_HTML)

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
