"""Add municipality to alerts

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-23

One city per alert. Existing rows stay Maceió.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "alerts",
        sa.Column(
            "municipality",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'Maceió'"),
        ),
    )
    op.create_check_constraint(
        "ck_alert_municipality",
        "alerts",
        "municipality IN ('Maceió', 'Recife')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_alert_municipality", "alerts", type_="check")
    op.drop_column("alerts", "municipality")
