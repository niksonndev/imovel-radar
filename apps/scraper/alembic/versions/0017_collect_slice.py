"""Status por fatia da varredura completa (`collect_slice`).

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-03

A última fatia inativava por (mercado, tipo) confiando que todas as outras
tinham passado. Com 7 das 14 fatias de venda do Recife clampando na página 100
da OLX, isso inativava anúncio vivo — que a varredura seguinte ressuscitava e
re-notificava. Agora a inativação só acontece quando todas as fatias do run
reportaram 'ok'.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collect_slice",
        sa.Column("run_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("market", sa.Text(), nullable=False),
        sa.Column("listing_kind", sa.Text(), nullable=False),
        sa.Column("slice_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint(
            "run_started_at", "market", "listing_kind", "slice_index"
        ),
    )


def downgrade() -> None:
    op.drop_table("collect_slice")
