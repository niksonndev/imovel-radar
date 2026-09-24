"""WhatsApp users: channel, jid, synthetic chat_id sequence, bot session

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-23

Telegram keeps ``users.chat_id`` as its primary key. WhatsApp rows use a
synthetic chat_id from ``whatsapp_user_id_seq`` (above any Telegram id) and
``whatsapp_jid`` as the stable external identity.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "channel",
            sa.Text(),
            nullable=False,
            server_default="telegram",
        ),
    )
    op.add_column("users", sa.Column("whatsapp_jid", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_users_channel",
        "users",
        "channel IN ('telegram', 'whatsapp')",
    )
    op.create_unique_constraint("uq_users_whatsapp_jid", "users", ["whatsapp_jid"])
    op.execute(
        "CREATE SEQUENCE IF NOT EXISTS whatsapp_user_id_seq "
        "START WITH 1000000000000000"
    )
    op.create_table(
        "bot_session",
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["chat_id"], ["users.chat_id"], name="fk_bot_session_chat_id"),
        sa.PrimaryKeyConstraint("chat_id", name="pk_bot_session"),
    )


def downgrade() -> None:
    op.drop_table("bot_session")
    op.execute("DROP SEQUENCE IF EXISTS whatsapp_user_id_seq")
    op.drop_constraint("uq_users_whatsapp_jid", "users", type_="unique")
    op.drop_constraint("ck_users_channel", "users", type_="check")
    op.drop_column("users", "whatsapp_jid")
    op.drop_column("users", "channel")
