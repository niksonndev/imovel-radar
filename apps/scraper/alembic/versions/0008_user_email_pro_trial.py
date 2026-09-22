"""Add email + email Pro trial claim columns on users

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-22

One-time Radar Pro trial via email signup while Stars checkout is paused.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("email_pro_trial_claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint("uq_users_email", "users", ["email"])


def downgrade() -> None:
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_column("users", "email_pro_trial_claimed_at")
    op.drop_column("users", "email")
