PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS listings (
    list_id              INTEGER PRIMARY KEY,
    title                TEXT,
    url                  TEXT,
    location             TEXT,
    municipality         TEXT,
    neighbourhood        TEXT,
    uf                   TEXT,
    ddd                  TEXT,
    current_price        INTEGER,
    real_estate_type     TEXT,
    size_m2              INTEGER,
    rooms                INTEGER,
    bathrooms            INTEGER,
    garage_spaces        INTEGER,
    re_complex_features  TEXT,
    re_type              TEXT,
    category_id          INTEGER,
    category_name        TEXT,
    is_active            BOOLEAN DEFAULT 1,
    is_professional      BOOLEAN DEFAULT 0,
    orig_list_time       INTEGER,
    first_seen_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen_at         DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS price_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    list_id      INTEGER NOT NULL REFERENCES listings(list_id),
    price        INTEGER NOT NULL,
    recorded_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS listing_images (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    list_id     INTEGER NOT NULL REFERENCES listings(list_id),
    url         TEXT NOT NULL,
    url_webp    TEXT,
    position    INTEGER
);

CREATE INDEX IF NOT EXISTS idx_neighbourhood ON listings(neighbourhood);
CREATE INDEX IF NOT EXISTS idx_current_price ON listings(current_price);
CREATE INDEX IF NOT EXISTS idx_is_active     ON listings(is_active);
CREATE INDEX IF NOT EXISTS idx_last_seen     ON listings(last_seen_at);
CREATE INDEX IF NOT EXISTS idx_price_list    ON price_history(list_id);
