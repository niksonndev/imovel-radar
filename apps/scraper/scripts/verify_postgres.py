"""Verificação end-to-end do upsert contra o Postgres local (pg-local).

Uso:
    uv run python scripts/verify_postgres.py

Requisitos:
- Container Postgres de pé (pg-local) e banco ``imovel_radar`` existente.
- ``DATABASE_URL`` apontando para o Postgres (default em config.py já usa o pg-local).
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from alembic.config import Config
from sqlmodel import Session

from alembic import command

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

import config  # noqa: E402
from collector.parser import RawAd  # noqa: E402
from database import engine  # noqa: E402
from database.models import Listing  # noqa: E402
from database.queries import upsert_listing  # noqa: E402


def _load_fixture(name: str) -> RawAd:
    fixture = ROOT / "tests" / "fixtures" / name
    return json.loads(fixture.read_text(encoding="utf-8"))


def main() -> None:
    logger.info("Target DB: %s", config.DATABASE_URL)

    # 1) Migrations end-to-end (mesmo caminho que o boot do app).
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    command.upgrade(cfg, "head")

    # 2) Upsert: insert e depois update pela mesma listing_id.
    listing = _load_fixture("parsed_olx_ad.json")
    with Session(engine) as session:
        upsert_listing(session, listing)
        session.commit()

    updated: RawAd = {**listing, "price_value": 2500, "old_price": listing["price_value"]}
    with Session(engine) as session:
        upsert_listing(session, updated)
        session.commit()
        stored = session.get(Listing, listing["listing_id"])
        assert stored is not None, "listing deveria existir após o upsert"
        assert stored.price_value == 2500, f"price_value={stored.price_value}"
        assert stored.old_price == listing["price_value"], f"old_price={stored.old_price}"
        assert stored.images == listing["images"], "images deveria ser preservado"
        session.delete(stored)
        session.commit()

    print("OK: upsert insert + update funcionando no Postgres (migrations também).")


if __name__ == "__main__":
    main()
