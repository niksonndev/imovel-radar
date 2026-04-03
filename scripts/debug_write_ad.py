from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

# `database/db.py` importa `config.py`, que exige TELEGRAM_BOT_TOKEN.
# Para este debug de insert (sem Telegram), criamos um valor dummy.

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "debug-token")

from database import create_tables

from database.db import get_connection

from database.queries import upsert_listing


logger = logging.getLogger(__name__)


ROOT = Path(__file__).resolve().parent.parent

JSON_PATH = ROOT / "parsed_debug_ad.json"


COLUMNS = [
    "listId",
    "url",
    "title",
    "priceValue",
    "oldPrice",
    "municipality",
    "neighbourhood",
    "category",
    "images",
    "properties",
]


def load_ads_from_json() -> list[dict[str, Any]]:

    raw = json.loads(JSON_PATH.read_text(encoding="utf-8"))

    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]

    if isinstance(raw, dict):
        return [raw]

    raise SystemExit(f"Formato inesperado em {JSON_PATH}: esperado list ou dict")


def ad_to_listing(ad: dict[str, Any]) -> dict[str, Any] | None:

    if ad.get("listId") is None:
        return None

    return {col: ad.get(col) for col in COLUMNS}


def main() -> None:

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Garante que o schema do SQLite existe antes de inserir.

    create_tables()

    ads = load_ads_from_json()

    listings: list[dict[str, Any]] = []

    for ad in ads:
        listing = ad_to_listing(ad)

        if listing is not None:
            listings.append(listing)

    logger.info("Tentando upsert de %s linhas (da JSON)", len(listings))

    if not listings:
        raise SystemExit("Nenhuma linha válida para inserir (listId ausente)")

    conn = get_connection()

    try:
        for listing in listings:
            upsert_listing(conn, listing)

        conn.commit()

    finally:
        conn.close()

    logger.info("Upsert concluído.")


if __name__ == "__main__":
    main()
