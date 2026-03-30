from .db import get_connection


def create_tables():
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS listings (
                listId         INTEGER PRIMARY KEY,
                active         INTEGER  NOT NULL  DEFAULT 1, -- 0 = sumiu do OLX
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
                first_seen_at  TEXT  -- ISO 8601, preenchido só na inserção, nunca sobrescrito
                updated_at     TEXT  -- atualizado no upsert diário
            );

            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id     INTEGER NOT NULL UNIQUE,
                created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        INTEGER NOT NULL,
                neighbourhood  TEXT,
                min_price      INTEGER,
                max_price      INTEGER,
                category       TEXT,
                active         INTEGER NOT NULL DEFAULT 1,
                created_at     TEXT    NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS alert_matches (
                alert_id    INTEGER NOT NULL,
                listing_id  INTEGER NOT NULL,
                notified_at TEXT    NOT NULL,
                PRIMARY KEY (alert_id, listing_id),
                FOREIGN KEY (alert_id) REFERENCES alerts(id),
                FOREIGN KEY (listing_id) REFERENCES listings(listId)
            );
            """
        )
        conn.commit()
    finally:
        conn.close()
