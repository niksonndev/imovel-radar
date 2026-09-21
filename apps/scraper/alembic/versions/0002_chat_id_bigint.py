"""chat_id BIGINT for Telegram ids > 2^31-1

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-21

Telegram user ids can exceed PostgreSQL INTEGER max (2_147_483_647).
``users.chat_id`` and ``alerts.chat_id`` must be BIGINT.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("alerts_chat_id_fkey", "alerts", type_="foreignkey")
    op.alter_column(
        "users",
        "chat_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )
    op.alter_column(
        "alerts",
        "chat_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )
    op.create_foreign_key(
        "alerts_chat_id_fkey",
        "alerts",
        "users",
        ["chat_id"],
        ["chat_id"],
    )


def downgrade() -> None:
    op.drop_constraint("alerts_chat_id_fkey", "alerts", type_="foreignkey")
    op.alter_column(
        "alerts",
        "chat_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
    op.alter_column(
        "users",
        "chat_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
    op.create_foreign_key(
        "alerts_chat_id_fkey",
        "alerts",
        "users",
        ["chat_id"],
        ["chat_id"],
    )
