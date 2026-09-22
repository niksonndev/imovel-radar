"""Add categories to alerts

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-22

Nullable JSON list of OLX listing.category values (e.g. Apartamentos, Casas).
NULL/empty means any category.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("categories", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("alerts", "categories")
