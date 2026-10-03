"""Guarda só a primeira imagem de cada anúncio.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-03

O array de imagens era 62% do peso da tabela (931 B de 2.299 B por linha) e
ninguém consome a galeria: o bot envia a primeira imagem e o frontend não usa
`listing.images`. O parser já passa a gravar só a primeira; aqui o passado é
aparado para o espaço liberado aparecer antes de dobrar o corpus.
"""

from __future__ import annotations

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE listing
           SET images = json_build_array(images ->> 0)
         WHERE json_typeof(images) = 'array'
           AND json_array_length(images) > 1
           AND images ->> 0 IS NOT NULL
        """
    )


def downgrade() -> None:
    # Sem volta: as imagens descartadas não existem mais em lugar nenhum.
    pass
