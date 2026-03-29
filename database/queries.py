from __future__ import annotations

import sqlite3

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
