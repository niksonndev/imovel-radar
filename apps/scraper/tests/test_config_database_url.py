from config import normalize_database_url


def test_normalize_plain_postgresql_to_psycopg() -> None:
    assert (
        normalize_database_url("postgresql://u:p@host/db")
        == "postgresql+psycopg://u:p@host/db"
    )


def test_normalize_postgres_scheme() -> None:
    assert (
        normalize_database_url("postgres://u:p@host/db")
        == "postgresql+psycopg://u:p@host/db"
    )


def test_normalize_psycopg2_dialect() -> None:
    assert (
        normalize_database_url("postgresql+psycopg2://u:p@host/db")
        == "postgresql+psycopg://u:p@host/db"
    )


def test_normalize_leaves_psycopg_alone() -> None:
    url = "postgresql+psycopg://u:p@host/db?sslmode=require"
    assert normalize_database_url(url) == url
