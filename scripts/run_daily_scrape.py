from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

# `config.py` exige TELEGRAM_BOT_TOKEN ao importar `database/db.py` e `scraper/olx_scraper.py`.
# Este script roda via scheduler externo e não precisa do bot; então garantimos um dummy.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "debug-token")

from database.db import get_connection
from database import create_tables
from scraper.olx_scraper import search_all_rent_maceio

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT / "logs"
LOG_FILE = LOGS_DIR / "scrape.log"

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


def setup_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Evita duplicar handlers quando rodar em notebooks/testes.
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    root_logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(fmt)
    root_logger.addHandler(file_handler)


def ad_to_row(ad: dict[str, Any]) -> tuple[Any, ...] | None:
    # `listId` é o PRIMARY KEY INTEGER da tabela.
    if ad.get("listId") is None:
        return None
    return tuple(ad.get(col) for col in COLUMNS)


def run_insert_batch(ads: list[dict[str, Any]]) -> tuple[int, int, int, int]:
    total_fetched = len(ads)
    total_inserted = 0
    total_skipped = 0
    total_errors = 0

    conn = get_connection()
    try:
        cur = conn.cursor()
        for idx, ad in enumerate(ads, start=1):
            row = ad_to_row(ad)
            list_id = ad.get("listId")

            if row is None:
                total_skipped += 1
                logger.info(
                    "[%s/%s] Skipped (sem listId)",
                    idx,
                    total_fetched,
                )
                continue

            try:
                cur.execute(INSERT_SQL, row)
                conn.commit()
                total_inserted += 1
                logger.info(
                    "[%s/%s] Inserted/Updated listId=%s",
                    idx,
                    total_fetched,
                    list_id,
                )
            except Exception:
                total_errors += 1
                conn.rollback()
                logger.exception(
                    "[%s/%s] Erro ao inserir listId=%s",
                    idx,
                    total_fetched,
                    list_id,
                )
    finally:
        conn.close()

    return (
        total_fetched,
        total_inserted,
        total_skipped,
        total_errors,
    )


def main() -> None:
    setup_logging()

    logger.info("Iniciando scrape diário do OLX...")
    create_tables()

    try:
        ads = asyncio.run(search_all_rent_maceio())
    except Exception:
        logger.exception("Falha ao buscar anúncios no OLX.")
        raise

    (
        total_fetched,
        total_inserted,
        total_skipped,
        total_errors,
    ) = run_insert_batch(ads)

    logger.info(
        "Resumo: fetched=%s inserted=%s skipped=%s errors=%s",
        total_fetched,
        total_inserted,
        total_skipped,
        total_errors,
    )
    print(
        f"Resumo: fetched={total_fetched} inserted={total_inserted} "
        f"skipped={total_skipped} errors={total_errors}"
    )


if __name__ == "__main__":
    main()

