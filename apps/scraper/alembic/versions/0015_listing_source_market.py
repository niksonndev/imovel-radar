"""Escopo da varredura no listing (`source_market`).

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-03

A inativação filtrava por `municipality`: a URL de Recife devolve a região
metropolitana inteira, então São Lourenço, Jaboatão, Olinda e companhia eram
coletados e nunca podiam sair do ar (medido: 17.336 anúncios em 188 municípios,
zero inativos). `source_market` guarda qual varredura viu o anúncio por último,
e é por ele que a inativação passa a filtrar.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "listing",
        sa.Column("source_market", sa.Text(), nullable=False, server_default=""),
    )
    # Backfill do que dá para inferir com segurança: as três cidades do registry.
    # As cidades satélites ficam com '' até a próxima varredura da região
    # adotá-las (todo walk reescreve a linha).
    op.execute(
        """
        UPDATE listing
           SET source_market = CASE municipality
                 WHEN 'Maceió' THEN 'maceio'
                 WHEN 'Recife' THEN 'recife'
                 WHEN 'Natal' THEN 'natal'
                 ELSE ''
               END
        """
    )
    op.create_index(
        "ix_listing_source_market_kind_active",
        "listing",
        ["source_market", "listing_kind", "active"],
    )


def downgrade() -> None:
    op.drop_index("ix_listing_source_market_kind_active", table_name="listing")
    op.drop_column("listing", "source_market")
