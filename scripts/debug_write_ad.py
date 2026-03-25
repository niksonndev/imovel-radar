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

INSERT_SQL = """
INSERT OR REPLACE INTO listings (
    listId, url, title, priceValue, oldPrice,
    municipality, neighbourhood, category, images, properties
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
""".strip()


def load_ads_from_json() -> list[dict[str, Any]]:
    raw = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        return [raw]
    raise SystemExit(f"Formato inesperado em {JSON_PATH}: esperado list ou dict")


def ad_to_row(ad: dict[str, Any]) -> tuple[Any, ...] | None:
    # listId é INTEGER PRIMARY KEY na tabela.
    if ad.get("listId") is None:
        return None
    return tuple(ad.get(col) for col in COLUMNS)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Garante que o schema do SQLite existe antes de inserir.
    create_tables()

    ads = load_ads_from_json()
    rows: list[tuple[Any, ...]] = []
    for ad in ads:
        row = ad_to_row(ad)
        if row is not None:
            rows.append(row)

    logger.info("Tentando inserir %s linhas (da JSON)", len(rows))
    if not rows:
        raise SystemExit("Nenhuma linha válida para inserir (listId ausente)")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.executemany(INSERT_SQL, rows)
        conn.commit()
    finally:
        conn.close()

    logger.info("Insert concluído.")


if __name__ == "__main__":
    main()

