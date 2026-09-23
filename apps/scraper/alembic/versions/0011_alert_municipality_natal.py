"""Allow Natal in alerts municipality check constraint

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-23
"""

from __future__ import annotations

from sqlalchemy import inspect

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    check_names = {
        constraint["name"] for constraint in inspector.get_check_constraints("alerts")
    }
    if "ck_alert_municipality" in check_names:
        op.drop_constraint("ck_alert_municipality", "alerts", type_="check")
    op.create_check_constraint(
        "ck_alert_municipality",
        "alerts",
        "municipality IN ('Maceió', 'Recife', 'Natal')",
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    check_names = {
        constraint["name"] for constraint in inspector.get_check_constraints("alerts")
    }
    if "ck_alert_municipality" in check_names:
        op.drop_constraint("ck_alert_municipality", "alerts", type_="check")
    op.create_check_constraint(
        "ck_alert_municipality",
        "alerts",
        "municipality IN ('Maceió', 'Recife')",
    )
