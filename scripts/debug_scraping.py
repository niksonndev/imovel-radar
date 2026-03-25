"""
Debug de scraping (OLX → SQLite).

Uso:
  python scripts/debug_scraping.py

O script:
- roda `scraper.olx_scraper.search_all_rent_maceio()`;
- garante o formato dos campos para a tabela `listings`;
- grava/atualiza os anúncios no SQLite (tabela `listings`).
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

from database import create_tables, get_connection
from scraper import olx_scraper
from scraper.parser import normalize_olx_listing


logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _json_if_needed(v: Any, *, fallback: str) -> str:
    """Converte lista/dict para JSON string; mantém strings como estão."""
    if v is None:
        return fallback
    if isinstance(v, str):
        return v
    return json.dumps(v, ensure_ascii=False)


def _ensure_row_format(ad: dict[str, Any]) -> dict[str, Any]:
    """
    `search_all_rent_maceio()` normalmente já retorna dados normalizados,
    mas existe um fallback em `parse_search_page` onde `properties/images`
    podem vir como lista (não JSON string). Aqui garantimos o formato.
    """

    props = ad.get("properties")
    imgs = ad.get("images")
    # Se já veio como string JSON, não re-normalizamos (evita "zerar" JSON já pronto).
    if not isinstance(props, str) or not isinstance(imgs, str):
        try:
            ad = normalize_olx_listing(ad)
        except Exception:
            # Último recurso: tenta converter apenas para JSON string.
            ad["properties"] = _json_if_needed(props, fallback="[]")
            ad["images"] = _json_if_needed(imgs, fallback="[]")
    else:
        # Mesmo estando como str, garantimos fallback para None.
        ad["properties"] = _json_if_needed(props, fallback="[]")
        ad["images"] = _json_if_needed(imgs, fallback="[]")

    # Proteção extra: listId deve ser inteiro (PRIMARY KEY).
    if ad.get("listId") is not None and not isinstance(ad.get("listId"), int):
        try:
            ad["listId"] = int(ad["listId"])
        except (TypeError, ValueError):
            pass

    return ad


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    create_tables()

    ads = await olx_scraper.search_all_rent_maceio()
    if not ads:
        logger.info("Nenhum anúncio retornado.")
        return

    rows: list[tuple[Any, ...]] = []
    for ad in ads:
        ad = _ensure_row_format(ad)
        list_id = ad.get("listId")
        if list_id is None:
            continue
        rows.append(
            (
                int(list_id),
                ad.get("url") or "",
                ad.get("title") or "",
                ad.get("priceValue"),
                ad.get("oldPrice"),
                ad.get("municipality") or "",
                ad.get("neighbourhood") or "",
                ad.get("category") or "",
                _json_if_needed(ad.get("images"), fallback="[]"),
                _json_if_needed(ad.get("properties"), fallback="[]"),
            )
        )

    if not rows:
        logger.info("Nenhum anúncio com listId válido para gravar.")
        return

    sql = """
        INSERT OR REPLACE INTO listings
            (listId, url, title, priceValue, oldPrice, municipality, neighbourhood, category, images, properties)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    conn = get_connection()
    try:
        # Descobre o arquivo do DB para log (sem depender de config.DB_PATH).
        db_path = conn.execute("PRAGMA database_list").fetchone()[2]

        with conn:
            conn.executemany(sql, rows)

        logger.info("Gravados/atualizados %s anúncios em %s", len(rows), db_path)
    finally:
        conn.close()
        await olx_scraper.close()


if __name__ == "__main__":
    asyncio.run(main())
