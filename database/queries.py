from __future__ import annotations

import sqlite3
from typing import Any, Sequence

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

GET_ALERT_BY_ID_SQL = """
SELECT id, user_id, alert_name, min_price, max_price, neighbourhoods,
       active, created_at
FROM alerts
WHERE id = ?
""".strip()

# Colunas devolvidas pelas buscas de listings. Declaradas uma única vez para
# que consumidores possam confiar na ordem/presença dos campos.
LISTING_COLUMNS = (
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
    "first_seen_at",
    "updated_at",
)
_LISTING_COLUMNS_SQL = ", ".join(LISTING_COLUMNS)


def upsert_listing(conn: sqlite3.Connection, listing: dict) -> None:
    conn.execute(UPSERT_LISTING_SQL, listing)


def get_maceio_neighbourhoods(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(GET_MACEIO_NEIGHBOURHOODS_SQL).fetchall()
    return [row[0] for row in rows]


def create_new_alert(conn: sqlite3.Connection, alert: dict) -> int:
    cur = conn.execute(INSERT_ALERT_SQL, alert)
    return cur.lastrowid


def get_alert_by_id(
    conn: sqlite3.Connection, alert_id: int
) -> sqlite3.Row | None:
    """Retorna a linha do alerta pelo id, ou None se não existir."""
    return conn.execute(GET_ALERT_BY_ID_SQL, (alert_id,)).fetchone()


def get_filtered_listings(
    conn: sqlite3.Connection,
    *,
    min_price: int | None = None,
    max_price: int | None = None,
    neighbourhoods: Sequence[str] | None = None,
    municipality: str | None = "Maceió",
    only_active: bool = True,
    limit: int | None = None,
) -> list[sqlite3.Row]:
    """Lê listings do cache local aplicando filtros opcionais.

    - ``min_price``/``max_price``: inclusivos; passe ``None`` para não filtrar.
    - ``neighbourhoods``: se vazio/``None``, não restringe por bairro.
    - ``municipality``: ``None`` desliga o filtro (útil em queries globais).
    - ``only_active``: se ``True``, considera apenas ``active = 1``.
    - ``limit``: se ``None``, não aplica ``LIMIT`` (devolve todos).

    Retorna ``list[sqlite3.Row]`` sem fazer parse de JSON (``images``/``properties``);
    a camada que consumir decide se normaliza.
    """
    where: list[str] = []
    params: list[Any] = []

    if only_active:
        where.append("active = 1")
    if municipality:
        where.append("municipality = ?")
        params.append(municipality)
    if isinstance(min_price, int):
        where.append("priceValue >= ?")
        params.append(min_price)
    if isinstance(max_price, int):
        where.append("priceValue <= ?")
        params.append(max_price)
    if neighbourhoods:
        placeholders = ", ".join(["?"] * len(neighbourhoods))
        where.append(f"neighbourhood IN ({placeholders})")
        params.extend(neighbourhoods)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    limit_sql = ""
    if isinstance(limit, int) and limit > 0:
        limit_sql = "LIMIT ?"
        params.append(limit)

    sql = (
        f"SELECT {_LISTING_COLUMNS_SQL} "
        f"FROM listings "
        f"{where_sql} "
        f"ORDER BY updated_at DESC, listId DESC "
        f"{limit_sql}"
    ).strip()

    return conn.execute(sql, params).fetchall()
