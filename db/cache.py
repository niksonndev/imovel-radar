from __future__ import annotations

from typing import Any

from db.database import get_connection, init_db


LISTING_FIELDS = [
    "title",
    "url",
    "location",
    "municipality",
    "neighbourhood",
    "uf",
    "ddd",
    "current_price",
    "real_estate_type",
    "size_m2",
    "rooms",
    "bathrooms",
    "garage_spaces",
    "re_complex_features",
    "re_type",
    "category_id",
    "category_name",
    "is_professional",
    "orig_list_time",
]


def _insert_images(conn, list_id: int, images: list[dict[str, Any]]) -> None:
    if not images:
        return
    conn.executemany(
        """
        INSERT INTO listing_images (list_id, url, url_webp, position)
        VALUES (?, ?, ?, ?)
        """,
        [
            (list_id, img.get("url"), img.get("url_webp"), img.get("position"))
            for img in images
            if img.get("url")
        ],
    )


def upsert_listing(data: dict[str, Any]) -> str:
    init_db()
    list_id = data["list_id"]
    images = data.get("images") or []

    with get_connection() as conn:
        with conn:
            existing = conn.execute(
                "SELECT * FROM listings WHERE list_id = ?",
                (list_id,),
            ).fetchone()

            if existing is None:
                conn.execute(
                    """
                    INSERT INTO listings (
                        list_id, title, url, location, municipality, neighbourhood, uf, ddd,
                        current_price, real_estate_type, size_m2, rooms, bathrooms, garage_spaces,
                        re_complex_features, re_type, category_id, category_name,
                        is_active, is_professional, orig_list_time
                    ) VALUES (
                        :list_id, :title, :url, :location, :municipality, :neighbourhood, :uf, :ddd,
                        :current_price, :real_estate_type, :size_m2, :rooms, :bathrooms, :garage_spaces,
                        :re_complex_features, :re_type, :category_id, :category_name,
                        1, :is_professional, :orig_list_time
                    )
                    """,
                    data,
                )
                if data.get("current_price") is not None:
                    conn.execute(
                        "INSERT INTO price_history (list_id, price) VALUES (?, ?)",
                        (list_id, data["current_price"]),
                    )
                _insert_images(conn, list_id, images)
                return "created"

            changed = False
            for field in LISTING_FIELDS:
                if existing[field] != data.get(field):
                    changed = True
                    break

            conn.execute(
                """
                UPDATE listings
                SET title = :title,
                    url = :url,
                    location = :location,
                    municipality = :municipality,
                    neighbourhood = :neighbourhood,
                    uf = :uf,
                    ddd = :ddd,
                    current_price = :current_price,
                    real_estate_type = :real_estate_type,
                    size_m2 = :size_m2,
                    rooms = :rooms,
                    bathrooms = :bathrooms,
                    garage_spaces = :garage_spaces,
                    re_complex_features = :re_complex_features,
                    re_type = :re_type,
                    category_id = :category_id,
                    category_name = :category_name,
                    is_professional = :is_professional,
                    orig_list_time = :orig_list_time,
                    is_active = 1,
                    last_seen_at = CURRENT_TIMESTAMP
                WHERE list_id = :list_id
                """,
                data,
            )

            old_price = existing["current_price"]
            new_price = data.get("current_price")
            if old_price != new_price and new_price is not None:
                conn.execute(
                    "INSERT INTO price_history (list_id, price) VALUES (?, ?)",
                    (list_id, new_price),
                )

            images_count = conn.execute(
                "SELECT COUNT(1) AS cnt FROM listing_images WHERE list_id = ?",
                (list_id,),
            ).fetchone()["cnt"]
            if images_count == 0:
                _insert_images(conn, list_id, images)

            return "updated" if changed else "unchanged"


def deactivate_missing(seen_ids: list[int]) -> int:
    init_db()
    with get_connection() as conn:
        with conn:
            if seen_ids:
                placeholders = ",".join("?" for _ in seen_ids)
                sql = (
                    "UPDATE listings "
                    "SET is_active = 0 "
                    "WHERE is_active = 1 AND list_id NOT IN (" + placeholders + ")"
                )
                cur = conn.execute(sql, seen_ids)
            else:
                cur = conn.execute(
                    "UPDATE listings SET is_active = 0 WHERE is_active = 1"
                )
            return int(cur.rowcount or 0)


def get_active_listings(filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    init_db()
    filters = filters or {}
    where = ["is_active = 1"]
    params: list[Any] = []

    if filters.get("municipality"):
        where.append("municipality = ?")
        params.append(filters["municipality"])
    if filters.get("neighbourhood"):
        where.append("neighbourhood = ?")
        params.append(filters["neighbourhood"])
    if filters.get("min_price") is not None:
        where.append("current_price >= ?")
        params.append(filters["min_price"])
    if filters.get("max_price") is not None:
        where.append("current_price <= ?")
        params.append(filters["max_price"])
    if filters.get("rooms") is not None:
        where.append("rooms = ?")
        params.append(filters["rooms"])
    if filters.get("min_size_m2") is not None:
        where.append("size_m2 >= ?")
        params.append(filters["min_size_m2"])

    sql = (
        "SELECT * FROM listings WHERE " + " AND ".join(where) + " "
        "ORDER BY last_seen_at DESC"
    )
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]
