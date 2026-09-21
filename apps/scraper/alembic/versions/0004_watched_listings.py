"""watched_listings for Acompanhar anúncio

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-21

Bot-owned table: user ↔ specific listing with baselines for price/active
change detection (ADR 0005).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watched_listings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("last_known_price", sa.Integer(), nullable=True),
        sa.Column(
            "last_known_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["chat_id"], ["users.chat_id"]),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.listing_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "chat_id",
            "listing_id",
            name="uq_watched_listings_chat_listing",
        ),
    )


def downgrade() -> None:
    op.drop_table("watched_listings")
