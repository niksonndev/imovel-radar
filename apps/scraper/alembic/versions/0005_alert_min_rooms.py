"""Add min_rooms to alerts

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-22

Nullable minimum bedrooms filter for alert matching. NULL means any;
listings without a rooms property still match when min_rooms is set.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("min_rooms", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("alerts", "min_rooms")
