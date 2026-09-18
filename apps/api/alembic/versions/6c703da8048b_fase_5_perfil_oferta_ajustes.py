"""fase 5 perfil oferta ajustes

Revision ID: 6c703da8048b
Revises: 92a9f082851f
Create Date: 2026-09-18 13:32:09.207985

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c703da8048b'
down_revision: Union[str, None] = '92a9f082851f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fecha o requisito P0 do doc 01 (rastreabilidade de origem em toda tabela
    # de catalogo de fonte) — fornecedor nunca teve `fonte`. Sempre
    # "declarado_produtor" nesta fase (ver docs/specs/05).
    op.add_column(
        "fornecedor",
        sa.Column("fonte", sa.String(length=120), nullable=False, server_default="declarado_produtor"),
    )

    # perfil_produtor/equipe viram singleton por fazenda (ver docs/specs/05) —
    # uma linha por fazenda_id.
    op.create_unique_constraint("uq_perfil_produtor_fazenda_id", "perfil_produtor", ["fazenda_id"])
    op.create_unique_constraint("uq_equipe_fazenda_id", "equipe", ["fazenda_id"])


def downgrade() -> None:
    op.drop_constraint("uq_equipe_fazenda_id", "equipe", type_="unique")
    op.drop_constraint("uq_perfil_produtor_fazenda_id", "perfil_produtor", type_="unique")
    op.drop_column("fornecedor", "fonte")
