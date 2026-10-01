import pytest

from shutdown_safety import require_remote_database


def test_shutdown_actions_reject_local_database_urls() -> None:
    for host in ("localhost", "127.0.0.1", "::1", "host.docker.internal", "postgres"):
        with pytest.raises(ValueError, match="banco local"):
            url_host = f"[{host}]" if ":" in host else host
            require_remote_database(f"postgresql+psycopg://user:pass@{url_host}/app")


def test_shutdown_actions_accept_remote_database_urls() -> None:
    require_remote_database("postgresql+psycopg://user:pass@ep.example.neon.tech/app")