"""Alembic environment — configured via ``[tool.alembic]`` in pyproject.toml.

During app initialization (main.py lifespan) and CLI (``alembic upgrade head``)
this script is executed. It: (1) ensures it finds the SQLModel models,
(2) points to the target metadata and (3) connects to the scraper database.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlmodel import SQLModel

from alembic import context

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config as app_config  # noqa: E402
import database.models  # noqa: F401,E402  (registers tables in SQLModel.metadata)
from database.db import engine  # noqa: E402

yaml_config = context.config

# Only configure logging when there is an existing .ini file (config via
# pyproject.toml doesn't have logging sections and the CLI may point to a
# non-existent alembic.ini by default).
_cfg_file = yaml_config.config_file_name
if _cfg_file and Path(_cfg_file).exists() and Path(_cfg_file).suffix == ".ini":
    fileConfig(_cfg_file, disable_existing_loggers=False)

target_metadata = SQLModel.metadata

DATABASE_URL = f"sqlite:///{app_config.DB_PATH}"


def run_migrations_offline() -> None:
    """Generate offline SQL without connection (``--sql`` mode)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations connecting to the app engine."""
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
