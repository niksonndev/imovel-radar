"""Add municipality to alerts

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-23

One city per alert. Existing rows stay Maceió.

Idempotent: the column/check may already exist if the schema was patched
outside Alembic before this revision was stamped.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("alerts")}
    if "municipality" not in columns:
        op.add_column(
            "alerts",
            sa.Column(
                "municipality",
                sa.Text(),
                nullable=False,
                server_default=sa.text("'Maceió'"),
            ),
        )

    check_names = {
        constraint["name"] for constraint in inspector.get_check_constraints("alerts")
    }
    if "ck_alert_municipality" not in check_names:
        op.create_check_constraint(
            "ck_alert_municipality",
            "alerts",
            "municipality IN ('Maceió', 'Recife')",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    check_names = {
        constraint["name"] for constraint in inspector.get_check_constraints("alerts")
    }
    if "ck_alert_municipality" in check_names:
        op.drop_constraint("ck_alert_municipality", "alerts", type_="check")

    columns = {col["name"] for col in inspector.get_columns("alerts")}
    if "municipality" in columns:
        op.drop_column("alerts", "municipality")
