"""Prévia e exclusão transacional de dados exclusivos do Telegram."""

from __future__ import annotations

import argparse

from sqlalchemy import text
from sqlalchemy.engine import Connection

import config
from database.db import get_engine
from shutdown_safety import require_remote_database

COUNT_QUERIES = {
    "users": "SELECT count(*) FROM users WHERE channel = 'telegram'",
    "alerts": """
        SELECT count(*) FROM alerts a
        JOIN users u USING (chat_id)
        WHERE u.channel = 'telegram'
    """,
    "alert_matches": """
        SELECT count(*) FROM alert_matches m
        JOIN alerts a ON a.id = m.alert_id
        JOIN users u USING (chat_id)
        WHERE u.channel = 'telegram'
    """,
    "watched_listings": """
        SELECT count(*) FROM watched_listings w
        JOIN users u USING (chat_id)
        WHERE u.channel = 'telegram'
    """,
    "bot_session": """
        SELECT count(*) FROM bot_session b
        JOIN users u USING (chat_id)
        WHERE u.channel = 'telegram'
    """,
    "assistant_usage": """
        SELECT count(*) FROM assistant_usage a
        JOIN users u USING (chat_id)
        WHERE u.channel = 'telegram'
    """,
}

DELETE_STATEMENTS = (
    """
    DELETE FROM alert_matches WHERE alert_id IN (
        SELECT a.id FROM alerts a JOIN users u USING (chat_id)
        WHERE u.channel = 'telegram'
    )
    """,
    """
    DELETE FROM alerts WHERE chat_id IN (
        SELECT chat_id FROM users WHERE channel = 'telegram'
    )
    """,
    """
    DELETE FROM watched_listings WHERE chat_id IN (
        SELECT chat_id FROM users WHERE channel = 'telegram'
    )
    """,
    """
    DELETE FROM bot_session WHERE chat_id IN (
        SELECT chat_id FROM users WHERE channel = 'telegram'
    )
    """,
    """
    DELETE FROM assistant_usage WHERE chat_id IN (
        SELECT chat_id FROM users WHERE channel = 'telegram'
    )
    """,
    "DELETE FROM users WHERE channel = 'telegram'",
)

def telegram_data_counts(connection: Connection) -> dict[str, int]:
    return {
        table: int(connection.execute(text(query)).scalar_one())
        for table, query in COUNT_QUERIES.items()
    }


def delete_telegram_data(
    connection: Connection,
    *,
    execute: bool,
    confirm_users: int | None,
) -> dict[str, int]:
    counts = telegram_data_counts(connection)
    if not execute:
        return counts
    if counts["users"] == 0:
        raise ValueError("nenhum usuário Telegram encontrado; exclusão cancelada")
    if confirm_users != counts["users"]:
        raise ValueError("a contagem confirmada não corresponde aos usuários Telegram")

    for statement in DELETE_STATEMENTS:
        connection.execute(text(statement))
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Excluir dados; sem esta opção, somente exibe contagens agregadas.",
    )
    parser.add_argument(
        "--confirm-users",
        type=int,
        help="Confirma a quantidade exata de usuários Telegram exibida na prévia.",
    )
    args = parser.parse_args()

    if args.execute and args.confirm_users is None:
        parser.error("--execute exige --confirm-users com a contagem verificada")
    if args.execute:
        try:
            require_remote_database(config.DATABASE_URL)
        except ValueError as error:
            parser.error(str(error))

    with get_engine().begin() as connection:
        counts = delete_telegram_data(
            connection,
            execute=args.execute,
            confirm_users=args.confirm_users,
        )

    for table, count in counts.items():
        print(f"{table}: {count}")
    if args.execute:
        print("Dados exclusivos do Telegram excluídos; usuários WhatsApp preservados.")
    else:
        print("Prévia apenas; nenhum dado foi alterado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())