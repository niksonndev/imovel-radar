"""Pagamentos do Radar Pro (Mercado Pago, Pix avulso + cartão).

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-03

Uma linha por cobrança criada. `referencia` é o `external_reference` enviado ao
PSP e carrega o chat_id, então não há login nem conferência manual para saber de
quem é o pagamento. `provider_payment_id` é único: webhook repetido não estende
o Pro duas vezes.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pagamento",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False, server_default="mercadopago"),
        sa.Column("referencia", sa.Text(), nullable=False),
        sa.Column("provider_payment_id", sa.Text(), nullable=True),
        sa.Column("valor_centavos", sa.Integer(), nullable=False),
        sa.Column("dias", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pendente"),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("pago_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["chat_id"], ["users.chat_id"], name="fk_pagamento_chat_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pagamento"),
        sa.UniqueConstraint("referencia", name="uq_pagamento_referencia"),
        sa.UniqueConstraint("provider_payment_id", name="uq_pagamento_provider_payment_id"),
        sa.CheckConstraint(
            "status IN ('pendente', 'pago', 'recusado', 'expirado')", name="ck_pagamento_status"
        ),
        sa.CheckConstraint("valor_centavos > 0", name="ck_pagamento_valor_positivo"),
        sa.CheckConstraint("dias > 0", name="ck_pagamento_dias_positivo"),
    )
    op.create_index("ix_pagamento_chat_id", "pagamento", ["chat_id"])
    op.create_index("ix_pagamento_status_criado_em", "pagamento", ["status", "criado_em"])


def downgrade() -> None:
    op.drop_index("ix_pagamento_status_criado_em", table_name="pagamento")
    op.drop_index("ix_pagamento_chat_id", table_name="pagamento")
    op.drop_table("pagamento")
