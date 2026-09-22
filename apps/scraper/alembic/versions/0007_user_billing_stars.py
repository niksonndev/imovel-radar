"""Add Radar Pro / Stars billing columns on users

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-22

plan, pro_until, stars charge id and subscription flag for freemium entitlement.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("plan", sa.Text(), nullable=False, server_default="free"),
    )
    op.add_column(
        "users",
        sa.Column("pro_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("stars_telegram_payment_charge_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "stars_subscription_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_check_constraint("ck_users_plan", "users", "plan IN ('free', 'pro')")


def downgrade() -> None:
    op.drop_constraint("ck_users_plan", "users", type_="check")
    op.drop_column("users", "stars_subscription_active")
    op.drop_column("users", "stars_telegram_payment_charge_id")
    op.drop_column("users", "pro_until")
    op.drop_column("users", "plan")
