"""Usuários Telegram ↔ linha em ``users`` (integridade de FK em ``alerts``)."""

from __future__ import annotations

import sqlite3


def ensure_user(conn: sqlite3.Connection, telegram_chat_id: int) -> int:
    """
    Garante uma linha em ``users`` para o chat_id do Telegram e devolve ``users.id``.

    Usado antes de inserir em ``alerts`` (``alerts.user_id`` referencia ``users.id``).
    """
    conn.execute(
        "INSERT INTO users (chat_id) VALUES (?) ON CONFLICT(chat_id) DO NOTHING",
        (telegram_chat_id,),
    )
    row = conn.execute(
        "SELECT id FROM users WHERE chat_id = ?",
        (telegram_chat_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError("Falha ao resolver users.id após INSERT de chat_id")
    return int(row[0])
