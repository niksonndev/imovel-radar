from __future__ import annotations

import sqlite3
from typing import Any, Sequence

from models import Listing, Alert

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

GET_MACEIO_NEIGHBOURHOODS_SQL = """
SELECT neighbourhood
FROM listings
WHERE municipality = 'Maceió'
  AND neighbourhood != ''
GROUP BY neighbourhood
ORDER BY COUNT(*) DESC
""".strip()

GET_FILTERED_LISTINGS_SQL = """
SELECT listId, url, title, priceValue, oldPrice,
       municipality, neighbourhood, category, images, properties
FROM listings
WHERE active = TRUE
  AND municipality = 'Maceió'
  AND priceValue >= ?
  AND priceValue <= ?
  AND neighbourhood IN ({placeholders})
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

GET_ALERT_BY_ID_SQL = """
SELECT id, user_id, alert_name, min_price, max_price, neighbourhoods,
       active, created_at
FROM alerts
WHERE id = ?
""".strip()

LIST_ALERTS_FOR_USER_SQL = """
SELECT id, user_id, alert_name, min_price, max_price, neighbourhoods,
       active, created_at
FROM alerts
WHERE user_id = ?
ORDER BY id DESC
""".strip()

GET_ALERT_FOR_USER_SQL = """
SELECT id, user_id, alert_name, min_price, max_price, neighbourhoods,
       active, created_at
FROM alerts
WHERE id = ? AND user_id = ?
""".strip()

INSERT_ALERT_MATCH_SQL = """
INSERT OR IGNORE INTO alert_matches (alert_id, listing_id, notified_at)
VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%S', 'now'))
""".strip()

# Base do SELECT de matches não notificados. Os filtros dinâmicos (preço,
# bairros, etc.) são concatenados em ``get_unnotified_matches_for_alert``.
_GET_UNNOTIFIED_MATCHES_SQL_BASE = """
SELECT l.listId, l.url, l.title, l.priceValue, l.oldPrice,
       l.municipality, l.neighbourhood, l.category, l.images, l.properties,
       l.first_seen_at, l.updated_at
FROM listings l
LEFT JOIN alert_matches am
    ON am.alert_id = ? AND am.listing_id = l.listId
WHERE am.listing_id IS NULL
  AND l.active = 1
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
    return Alert(**dict(row))


def list_alerts_for_user(conn: sqlite3.Connection, user_id: int) -> list[Alert]:
    """Lista todos os alertas de um usuário (interno), do mais recente ao mais antigo."""
    return conn.execute(LIST_ALERTS_FOR_USER_SQL, (user_id,)).fetchall()


def get_alert_for_user(conn: sqlite3.Connection, alert_id: int, user_id: int) -> Alert:
    """Retorna o alerta se existir e pertencer ao ``user_id`` interno."""
    return conn.execute(GET_ALERT_FOR_USER_SQL, (alert_id, user_id)).fetchone()


def delete_alert_for_user(
    conn: sqlite3.Connection, alert_id: int, user_id: int
) -> bool:
    """Apaga o alerta e os vínculos em ``alert_matches``; retorna ``True`` se removeu linha."""
    conn.execute("DELETE FROM alert_matches WHERE alert_id = ?", (alert_id,))
    cur = conn.execute(
        "DELETE FROM alerts WHERE id = ? AND user_id = ?",
        (alert_id, user_id),
    )
    return cur.rowcount > 0


def get_filtered_listings(
    conn: sqlite3.Connection,
    min_price: int,
    max_price: int,
    neighbourhoods: list[str],
) -> list[Listing]:
    placeholders = ",".join("?" * len(neighbourhoods))
    query = GET_FILTERED_LISTINGS_SQL.format(placeholders=placeholders)
    params = [min_price, max_price, *neighbourhoods]

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    return [Listing(**dict(row)) for row in rows]


def get_unnotified_matches_for_alert(
    conn: sqlite3.Connection,
    alert_id: int,
    *,
    min_price: int | None = None,
    max_price: int | None = None,
    neighbourhoods: Sequence[str] | None = None,
    municipality: str | None = "Maceió",
    since_iso: str | None = None,
    only_active: bool = True,
    limit: int | None = None,
) -> list[Listing]:
    """Listings que casam com o alerta e ainda NÃO estão em ``alert_matches``.

    Usa ``LEFT JOIN … IS NULL`` para filtrar anúncios já notificados para
    aquele alerta. ``since_iso``, se informado, aplica ``first_seen_at >= ?``
    como uma rede de segurança adicional.
    """
    where: list[str] = []
    params: list[Any] = [alert_id]

    # ``only_active`` já está no base, mas mantém a flag para permitir reuso
    # em relatórios que queiram incluir inativos.
    base = _GET_UNNOTIFIED_MATCHES_SQL_BASE
    if not only_active:
        base = base.replace("\n  AND l.active = 1", "")

    if municipality:
        where.append("l.municipality = ?")
        params.append(municipality)
    if isinstance(min_price, int):
        where.append("l.priceValue >= ?")
        params.append(min_price)
    if isinstance(max_price, int):
        where.append("l.priceValue <= ?")
        params.append(max_price)
    if neighbourhoods:
        placeholders = ", ".join(["?"] * len(neighbourhoods))
        where.append(f"l.neighbourhood IN ({placeholders})")
        params.extend(neighbourhoods)
    if since_iso:
        where.append("l.first_seen_at >= ?")
        params.append(since_iso)

    where_sql = ""
    if where:
        where_sql = " AND " + " AND ".join(where)

    limit_sql = ""
    if isinstance(limit, int) and limit > 0:
        limit_sql = " LIMIT ?"
        params.append(limit)

    sql = base + where_sql + " ORDER BY l.first_seen_at DESC, l.listId DESC" + limit_sql
    return conn.execute(sql, params).fetchall()


def mark_listings_notified(
    conn: sqlite3.Connection,
    alert_id: int,
    listing_ids: list[int],
) -> None:
    conn.executemany(
        INSERT_ALERT_MATCH_SQL, [(alert_id, listing_id) for listing_id in listing_ids]
    )
