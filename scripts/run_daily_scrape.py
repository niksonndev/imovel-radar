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
INSERT INTO listings (
    listId, url, title, priceValue, oldPrice,
    municipality, neighbourhood, category, images, properties,
    first_seen_at
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
ON CONFLICT(listId) DO UPDATE SET
    url = excluded.url,
    title = excluded.title,
    priceValue = excluded.priceValue,
    oldPrice = excluded.oldPrice,
    municipality = excluded.municipality,
    neighbourhood = excluded.neighbourhood,
    category = excluded.category,
    images = excluded.images,
    properties = excluded.properties,
    active = 1
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
        try:
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
                    total_inserted += 1
                    logger.debug(
                        "[%s/%s] Inserted/Updated listId=%s",
                        idx,
                        total_fetched,
                        list_id,
                    )
                except Exception:
                    total_errors += 1
                    logger.exception(
                        "[%s/%s] Erro ao inserir listId=%s",
                        idx,
                        total_fetched,
                        list_id,
                    )
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()
    finally:
        conn.close()

    return (
        total_fetched,
        total_inserted,
        total_skipped,
        total_errors,
    )


def deactivate_missing(scraped_ids: set[int]) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT listId FROM listings WHERE active = 1;")
        active_in_db = {int(row[0]) for row in cur.fetchall()}

        missing_ids = active_in_db - scraped_ids
        if not missing_ids:
            return 0

        cur.executemany(
            "UPDATE listings SET active = 0 WHERE listId = ?;",
            [(list_id,) for list_id in missing_ids],
        )
        conn.commit()
        return len(missing_ids)
    finally:
        conn.close()


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

    scraped_ids = {int(ad["listId"]) for ad in ads if ad.get("listId") is not None}
    total_deactivated = deactivate_missing(scraped_ids)

    logger.info(
        "Resumo: fetched=%s inserted=%s skipped=%s errors=%s deactivated=%s",
        total_fetched,
        total_inserted,
        total_skipped,
        total_errors,
        total_deactivated,
    )
    print(
        f"Resumo: fetched={total_fetched} inserted={total_inserted} "
        f"skipped={total_skipped} errors={total_errors} deactivated={total_deactivated}"
    )


if __name__ == "__main__":
    main()

