import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import UUIDPrimaryKeyMixin


class TipoExecucao(str, enum.Enum):
    INGESTAO_CLIMA = "ingestao_clima"
    INGESTAO_SATELITE = "ingestao_satelite"
    INDICE_VEGETACAO = "indice_vegetacao"
    DIAGNOSTICO = "diagnostico"
    CENARIO = "cenario"


class StatusExecucao(str, enum.Enum):
    SUCESSO = "sucesso"
    FALHA = "falha"
    PARCIAL = "parcial"
    EM_ANDAMENTO = "em_andamento"


class ExecucaoProcessamento(UUIDPrimaryKeyMixin, Base):
    """Manifesto de execucao (docs/specs/00): rastreia fontes, versao e
    parametros usados por toda execucao de ingestao/processamento/diagnostico/
    cenario, permitindo que o usuario veja o que sustenta cada conclusao."""

    __tablename__ = "execucao_processamento"

    tipo: Mapped[TipoExecucao] = mapped_column(Enum(TipoExecucao, name="tipo_execucao"), nullable=False)
    entrada_fontes: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    parametros: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    versao_pipeline: Mapped[str] = mapped_column(String(50), nullable=False)
    iniciado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[StatusExecucao] = mapped_column(
        Enum(StatusExecucao, name="status_execucao"), nullable=False, default=StatusExecucao.EM_ANDAMENTO
    )
    saida_referencias: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
