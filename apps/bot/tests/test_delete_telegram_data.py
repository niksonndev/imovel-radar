from sqlalchemy import create_engine, text

from delete_telegram_data import delete_telegram_data


def create_database():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys = ON"))
        connection.execute(
            text("CREATE TABLE users (chat_id INTEGER PRIMARY KEY, channel TEXT NOT NULL)")
        )
        connection.execute(
            text(
                "CREATE TABLE alerts (id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL "
                "REFERENCES users(chat_id))"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE alert_matches (alert_id INTEGER PRIMARY KEY "
                "REFERENCES alerts(id))"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE watched_listings (id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL "
                "REFERENCES users(chat_id))"
            )
        )
        for table in ("bot_session", "assistant_usage"):
            connection.execute(
                text(
                    f"CREATE TABLE {table} (chat_id INTEGER PRIMARY KEY "
                    "REFERENCES users(chat_id))"
                )
            )
        connection.execute(
            text("INSERT INTO users VALUES (10, 'telegram'), (20, 'whatsapp')")
        )
        connection.execute(text("INSERT INTO alerts VALUES (100, 10), (200, 20)"))
        connection.execute(text("INSERT INTO alert_matches VALUES (100), (200)"))
        connection.execute(text("INSERT INTO watched_listings VALUES (1, 10), (2, 20)"))
        connection.execute(text("INSERT INTO bot_session VALUES (10), (20)"))
        connection.execute(text("INSERT INTO assistant_usage VALUES (10), (20)"))
    return engine


def test_preview_counts_telegram_data_without_deleting():
    engine = create_database()
    with engine.begin() as connection:
        counts = delete_telegram_data(
            connection,
            execute=False,
            confirm_users=None,
        )

    assert counts == {
        "users": 1,
        "alerts": 1,
        "alert_matches": 1,
        "watched_listings": 1,
        "bot_session": 1,
        "assistant_usage": 1,
    }
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM users")).scalar_one() == 2
    engine.dispose()


def test_delete_removes_only_telegram_rows_and_dependents():
    engine = create_database()
    with engine.begin() as connection:
        counts = delete_telegram_data(
            connection,
            execute=True,
            confirm_users=1,
        )

    with engine.connect() as connection:
        assert connection.execute(text("SELECT channel FROM users")).scalar_one() == "whatsapp"
        tables = ("alerts", "alert_matches", "watched_listings", "bot_session", "assistant_usage")
        for table in tables:
            assert connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 1
    assert counts["users"] == 1
    engine.dispose()