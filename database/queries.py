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

GET_MACEIO_NEIGHBOURHOODS_SQL = """
SELECT neighbourhood
FROM listings
WHERE municipality = 'Maceió'
  AND neighbourhood != ''
GROUP BY neighbourhood
ORDER BY COUNT(*) DESC
""".strip()

INSERT_ALERT_SQL = """
INSERT INTO alerts (
    user_id, alert_name, min_price, max_price, neighbourhoods, created_at
)
VALUES (
    :user_id, :alert_name, :min_price, :max_price, :neighbourhoods,
    strftime('%Y-%m-%dT%H:%M:%S', 'now')
)
""".strip()


def upsert_listing(conn: sqlite3.Connection, listing: dict) -> None:
    conn.execute(UPSERT_LISTING_SQL, listing)


def get_maceio_neighbourhoods(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(GET_MACEIO_NEIGHBOURHOODS_SQL).fetchall()
    return [row[0] for row in rows]


def create_new_alert(conn: sqlite3.Connection, alert: dict) -> int:
    cur = conn.execute(INSERT_ALERT_SQL, alert)
    return cur.lastrowid
