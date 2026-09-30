"""Daily assistant usage quotas and aggregate token telemetry.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_usage",
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("audio_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("audio_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["chat_id"], ["users.chat_id"], name="fk_assistant_usage_chat_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("chat_id", "usage_date", name="pk_assistant_usage"),
        sa.CheckConstraint("message_count >= 0", name="ck_assistant_usage_messages_nonnegative"),
        sa.CheckConstraint("audio_count >= 0", name="ck_assistant_usage_audio_nonnegative"),
        sa.CheckConstraint("input_tokens >= 0", name="ck_assistant_usage_input_tokens_nonnegative"),
        sa.CheckConstraint(
            "output_tokens >= 0", name="ck_assistant_usage_output_tokens_nonnegative"
        ),
        sa.CheckConstraint("total_tokens >= 0", name="ck_assistant_usage_tokens_nonnegative"),
    )
    op.create_index("ix_assistant_usage_usage_date", "assistant_usage", ["usage_date"])


def downgrade() -> None:
    op.drop_index("ix_assistant_usage_usage_date", table_name="assistant_usage")
    op.drop_table("assistant_usage")
