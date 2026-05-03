from __future__ import annotations

import sqlite3
from typing import Any, Iterable, Sequence

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

GET_ACTIVE_ALERTS_WITH_CHAT_SQL = """
SELECT a.id, a.alert_name, a.min_price, a.max_price, a.neighbourhoods,
       u.chat_id
FROM alerts a
JOIN users u ON u.id = a.user_id
WHERE a.active = 1
ORDER BY a.id
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


def list_alerts_for_user(
    conn: sqlite3.Connection, user_id: int
) -> list[sqlite3.Row]:
    """Lista todos os alertas de um usuário (interno), do mais recente ao mais antigo."""
    return conn.execute(LIST_ALERTS_FOR_USER_SQL, (user_id,)).fetchall()


def get_alert_for_user(
    conn: sqlite3.Connection, alert_id: int, user_id: int
) -> sqlite3.Row | None:
    """Retorna o alerta se existir e pertencer ao ``user_id`` interno."""
    return conn.execute(
        GET_ALERT_FOR_USER_SQL, (alert_id, user_id)
    ).fetchone()


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


def get_active_alerts_with_chat(
    conn: sqlite3.Connection,
) -> list[sqlite3.Row]:
    """Lista todos os alertas ativos com ``chat_id`` do dono para notificação."""
    return conn.execute(GET_ACTIVE_ALERTS_WITH_CHAT_SQL).fetchall()


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
) -> list[sqlite3.Row]:
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

    sql = (
        base
        + where_sql
        + " ORDER BY l.first_seen_at DESC, l.listId DESC"
        + limit_sql
    )
    return conn.execute(sql, params).fetchall()


def mark_listings_notified(
    conn: sqlite3.Connection,
    alert_id: int,
    listing_ids: Iterable[int],
) -> int:
    """Grava em ``alert_matches`` que estes listings já foram notificados.

    ``INSERT OR IGNORE`` preserva idempotência (a PK composta evita duplicatas).
    Retorna o número de linhas realmente inseridas.
    """
    pairs = [(alert_id, int(lid)) for lid in listing_ids]
    if not pairs:
        return 0
    cur = conn.executemany(INSERT_ALERT_MATCH_SQL, pairs)
    return cur.rowcount or 0
