"""listing_kind on listing and alerts

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-21

Discriminator for aluguel vs venda on both scraped listings and user alerts.
Existing rows backfill to ``aluguel``.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "listing",
        sa.Column(
            "listing_kind",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'aluguel'"),
        ),
    )
    op.create_check_constraint(
        "ck_listing_listing_kind",
        "listing",
        "listing_kind IN ('aluguel', 'venda')",
    )

    op.add_column(
        "alerts",
        sa.Column(
            "listing_kind",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'aluguel'"),
        ),
    )
    op.create_check_constraint(
        "ck_alert_listing_kind",
        "alerts",
        "listing_kind IN ('aluguel', 'venda')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_alert_listing_kind", "alerts", type_="check")
    op.drop_column("alerts", "listing_kind")
    op.drop_constraint("ck_listing_listing_kind", "listing", type_="check")
    op.drop_column("listing", "listing_kind")
