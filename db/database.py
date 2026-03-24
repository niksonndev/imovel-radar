from __future__ import annotations

import sqlite3
from pathlib import Path

import config


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "db" / "schema.sql"


def _sqlite_path_from_database_url(database_url: str) -> str:
    prefix = "sqlite+aiosqlite:///"
    if database_url.startswith(prefix):
        raw_path = database_url[len(prefix):]
        return str(Path(raw_path).resolve())
    if database_url.startswith("sqlite:///"):
        raw_path = database_url[len("sqlite:///"):]
        return str(Path(raw_path).resolve())
    raise ValueError(f"DATABASE_URL SQLite nao suportada: {database_url}")


def get_connection() -> sqlite3.Connection:
    db_path = _sqlite_path_from_database_url(config.DATABASE_URL)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db() -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection() as conn:
        conn.executescript(schema)
