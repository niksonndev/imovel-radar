from __future__ import annotations

import sqlite3


def ensure_user(conn: sqlite3.Connection, telegram_chat_id: int) -> int:
    """Ensure a user exists, keyed by the Telegram chat_id (its primary key).

    Returns the chat_id itself, which is the user's identity.
    """
    conn.execute(
        "INSERT OR IGNORE INTO users (chat_id) VALUES (?)",
        (telegram_chat_id,),
    )
    return telegram_chat_id