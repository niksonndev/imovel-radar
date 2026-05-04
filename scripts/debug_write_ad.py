"""
Script de debug para inserir um anúncio no banco de dados local.

Uso:
    python -m scripts.debug_write_ad

Lê o arquivo `parsed_debug_ad.json` na raiz do projeto e faz upsert
do registro na tabela `listings` via SQLite.

O arquivo JSON deve conter um único objeto com os campos do modelo
Listing (listId, url, title, priceValue, etc.). O campo `listId`
é obrigatório — sem ele o upsert não é executado.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

# `database/db.py` importa `config.py`, que exige TELEGRAM_BOT_TOKEN.
# Para este debug de insert (sem Telegram), criamos um valor dummy.

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "debug-token")

from database import create_tables

from database.db import get_connection

from database.queries import upsert_listing

from utils.models import Listing


logger = logging.getLogger(__name__)


ROOT = Path(__file__).resolve().parent.parent

JSON_PATH = ROOT / "parsed_debug_ad.json"


def load_ad_from_json() -> Listing:
    raw = json.loads(JSON_PATH.read_text(encoding="utf-8"))

    if not isinstance(raw, dict):
        raise SystemExit(f"Formato inesperado em {JSON_PATH}: esperado dict")

    return Listing(**raw)


def main() -> None:
    # Logging local para script de suporte; mantém rastreabilidade de execuções.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Garante que o schema do SQLite existe antes de inserir.

    create_tables()

    listing = load_ad_from_json()

    logger.info("Tentando upsert de %s linhas (da JSON)", listing)

    if not listing:
        raise SystemExit("Nenhuma linha válida para inserir (listId ausente)")

    # Uma única transação para batch: commit ao fim ou rollback implícito em erro.
    conn = get_connection()

    try:
        upsert_listing(conn, listing)
        conn.commit()

    finally:
        conn.close()

    logger.info("Upsert concluído.")


if __name__ == "__main__":
    main()
