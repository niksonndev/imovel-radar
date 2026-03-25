from .db import get_connection


def create_tables():
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS listings (
                listId         INTEGER PRIMARY KEY,
                active         INTEGER  NOT NULL  DEFAULT 1,
                url            TEXT,
                title          TEXT,
                priceValue     INTEGER,
                oldPrice       INTEGER,
                municipality   TEXT,
                neighbourhood  TEXT,
                category       TEXT,
                images         TEXT, -- JSON array de URLs
                properties     TEXT  -- JSON bruto com category, real_estate_type,
                                     -- condominio, iptu, size, rooms, bathrooms,
                                     -- garage_spaces, re_types
                first_seen_at  TEXT  -- ISO 8601, ex: "2026-03-25T12:16:22"
            );
            """
        )
        conn.commit()
    finally:
        conn.close()
