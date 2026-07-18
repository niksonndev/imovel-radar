from __future__ import annotations

import sqlite3
from typing import cast

from models import Alert, AlertWithChat, Listing

GET_MACEIO_NEIGHBOURHOODS_SQL = """
SELECT neighbourhood
FROM listings
WHERE municipality = 'Maceió'
  AND neighbourhood != ''
GROUP BY neighbourhood
ORDER BY COUNT(*) DESC
""".strip()

GET_LISTINGS_BY_IDS_SQL = """
SELECT listId, url, title, priceValue, oldPrice,
       municipality, neighbourhood, category, images, properties
FROM listings
WHERE listId IN ({placeholders})
  AND active = TRUE
""".strip()

GET_FILTERED_LISTINGS_SQL = """
SELECT l.listId, l.url, l.title, l.priceValue, l.oldPrice,
       l.municipality, l.neighbourhood, l.category, l.images, l.properties
FROM listings l
LEFT JOIN alert_matches am
  ON am.listing_id = l.listId AND am.alert_id = ?
WHERE l.active = TRUE
  AND l.municipality = 'Maceió'
  AND l.priceValue >= ?
  AND l.priceValue <= ?
  AND l.neighbourhood IN ({placeholders})
  AND am.listing_id IS NULL
""".strip()

GET_ALERT_FOR_USER_SQL = """
SELECT id, user_id, alert_name, min_price, max_price, neighbourhoods,
       active, created_at
FROM alerts
WHERE id = ? AND user_id = ?
""".strip()

GET_ALERT_BY_ID_SQL = """
SELECT id, user_id, alert_name, min_price, max_price, neighbourhoods,
       active, created_at
FROM alerts
WHERE id = ?
""".strip()

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
    active = TRUE,
    updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now')
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

INSERT_ALERT_MATCH_SQL = """
INSERT OR IGNORE INTO alert_matches (alert_id, listing_id, notified_at)
VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%S', 'now'))
""".strip()

LIST_ALERTS_FOR_USER_SQL = """
SELECT id, user_id, alert_name, min_price, max_price, neighbourhoods,
       active, created_at
FROM alerts
WHERE user_id = ?
ORDER BY id DESC
""".strip()


LIST_ACTIVE_ALERTS_WITH_CHAT_SQL = """
SELECT a.id, a.user_id, a.alert_name, a.min_price, a.max_price, a.neighbourhoods,
       a.active, a.created_at, u.chat_id
FROM alerts a
JOIN users u ON u.id = a.user_id
WHERE a.active = TRUE
ORDER BY a.id
""".strip()


def upsert_listing(conn: sqlite3.Connection, listing: Listing) -> None:
    conn.execute(UPSERT_LISTING_SQL, listing)


def get_maceio_neighbourhoods(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(GET_MACEIO_NEIGHBOURHOODS_SQL).fetchall()
    return [row[0] for row in rows]


def create_new_alert(conn: sqlite3.Connection, alert_data: dict) -> int:
    cur = conn.execute(INSERT_ALERT_SQL, alert_data)
    last_id = cur.lastrowid
    if last_id is None:
        raise RuntimeError("Falha ao obter ID do alerta inserido")
    return last_id


def get_alert_by_id(conn: sqlite3.Connection, alert_id: int) -> Alert:
    row = conn.execute(GET_ALERT_BY_ID_SQL, (alert_id,)).fetchone()
    return cast(Alert, dict(row))


def list_alerts_for_user(conn: sqlite3.Connection, user_id: int) -> list[Alert]:
    """Lista todos os alertas de um usuário (interno), do mais recente ao mais antigo."""
    return conn.execute(LIST_ALERTS_FOR_USER_SQL, (user_id,)).fetchall()


def get_alert_for_user(conn: sqlite3.Connection, alert_id: int, user_id: int) -> Alert:
    """Retorna o alerta se existir e pertencer ao ``user_id`` interno."""
    row = conn.execute(GET_ALERT_FOR_USER_SQL, (alert_id, user_id)).fetchone()
    return cast(Alert, dict(row))


def delete_alert_for_user(conn: sqlite3.Connection, alert_id: int, user_id: int) -> bool:
    """Apaga o alerta e os vínculos em ``alert_matches``; retorna ``True`` se removeu linha."""
    conn.execute("DELETE FROM alert_matches WHERE alert_id = ?", (alert_id,))
    cur = conn.execute(
        "DELETE FROM alerts WHERE id = ? AND user_id = ?",
        (alert_id, user_id),
    )
    return cur.rowcount > 0


def get_filtered_listings(
    conn: sqlite3.Connection,
    alert_id: int,
    min_price: int,
    max_price: int,
    neighbourhoods: list[str],
) -> list[Listing]:
    placeholders = ",".join("?" * len(neighbourhoods))
    query = GET_FILTERED_LISTINGS_SQL.format(placeholders=placeholders)
    params = [alert_id, min_price, max_price, *neighbourhoods]

    listings = conn.execute(query, params).fetchall()
    return cast(list[Listing], [dict(listing) for listing in listings])


def get_listings_by_ids(
    conn: sqlite3.Connection,
    listing_ids: list[int],
) -> list[Listing]:
    if not listing_ids:
        return []
    placeholders = ",".join("?" * len(listing_ids))
    query = GET_LISTINGS_BY_IDS_SQL.format(placeholders=placeholders)
    rows = conn.execute(query, listing_ids).fetchall()
    by_id = {row["listId"]: dict(row) for row in rows}
    # reordena conforme listing_ids, pulando os que sumiram (inativos)
    return cast(list[Listing], [by_id[lid] for lid in listing_ids if lid in by_id])


def mark_listings_notified(
    conn: sqlite3.Connection,
    alert_id: int,
    listing_ids: list[int],
) -> None:
    conn.executemany(INSERT_ALERT_MATCH_SQL, [(alert_id, listing_id) for listing_id in listing_ids])


def list_active_alerts_with_chat(conn: sqlite3.Connection) -> list[AlertWithChat]:
    listings = conn.execute(LIST_ACTIVE_ALERTS_WITH_CHAT_SQL).fetchall()
    return cast(list[AlertWithChat], [dict(listing) for listing in listings])
