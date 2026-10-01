"""Proteções comuns para ações de encerramento Telegram."""

from sqlalchemy.engine import make_url

LOCAL_DATABASE_HOSTS = {
    None,
    "localhost",
    "localhost.localdomain",
    "127.0.0.1",
    "::1",
    "host.docker.internal",
    "postgres",
    "db",
}


def require_remote_database(database_url: str) -> None:
    if make_url(database_url).host in LOCAL_DATABASE_HOSTS:
        raise ValueError("recusa executar ação de encerramento em banco local")