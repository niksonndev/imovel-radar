"""market_snapshot and listing aggregate index

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-23

Daily JSON snapshot of active listings, plus an index for the aggregate query.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "market_snapshot" not in inspector.get_table_names():
        op.create_table(
            "market_snapshot",
            sa.Column("collected_on", sa.Date(), nullable=False),
            sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.PrimaryKeyConstraint("collected_on"),
        )

    indexes = {index["name"] for index in inspector.get_indexes("listing")}
    if "ix_listing_active_kind_municipality" not in indexes:
        op.create_index(
            "ix_listing_active_kind_municipality",
            "listing",
            ["active", "listing_kind", "municipality"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("listing")}
    if "ix_listing_active_kind_municipality" in indexes:
        op.drop_index("ix_listing_active_kind_municipality", table_name="listing")
    if "market_snapshot" in inspector.get_table_names():
        op.drop_table("market_snapshot")
