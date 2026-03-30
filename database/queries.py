from __future__ import annotations

import json
import sqlite3
from datetime import datetime

UPSERT_LISTING_SQL = """
INSERT INTO listings (
    listId, url, title, priceValue, oldPrice,
    municipality, neighbourhood, category, images, properties,
    active, first_seen_at, updated_at
)
VALUES (
    :listId, :url, :title, :priceValue, :oldPrice,
    :municipality, :neighbourhood, :category, :images, :properties,
    1,
    strftime('%Y-%m-%dT%H:%M:%S', 'now'),
    strftime('%Y-%m-%dT%H:%M:%S', 'now')
)
ON CONFLICT(listId) DO UPDATE SET
    priceValue = excluded.priceValue,
    oldPrice = excluded.oldPrice,
    active = 1,
    updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now')
""".strip()


def upsert_listing(conn: sqlite3.Connection, listing: dict) -> None:
    conn.execute(UPSERT_LISTING_SQL, listing)


def create_new_alert(conn: sqlite3.Connection, chat_id: int, draft: dict) -> int:
    """Garante usuário por chat_id e insere linha em alerts; não faz commit."""
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (chat_id) VALUES (?);", (chat_id,))
    cur.execute("SELECT id FROM users WHERE chat_id = ?;", (chat_id,))
    row = cur.fetchone()
    if row is None:
        msg = "Não foi possível identificar o usuário no banco."
        raise RuntimeError(msg)

    user_id = int(row["id"])
    nb_list = sorted(draft.get("neighbourhoods") or [])
    neighbourhoods_json = json.dumps(nb_list, ensure_ascii=False)
    created = datetime.utcnow().replace(microsecond=0).isoformat()

    cur.execute(
        """
        INSERT INTO alerts (
            user_id, alert_name, min_price, max_price,
            neighbourhoods, listing_transaction, active, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 1, ?);
        """,
        (
            user_id,
            draft.get("alert_name"),
            draft.get("min_price"),
            draft.get("max_price"),
            neighbourhoods_json,
            draft.get("transaction", "sale"),
            created,
        ),
    )
    return int(cur.lastrowid)