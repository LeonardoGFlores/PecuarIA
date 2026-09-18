import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import UUIDPrimaryKeyMixin
from app.models.vegetacao import TipoIndiceVegetacao


class ClassificacaoTendencia(str, enum.Enum):
    QUEDA = "queda"
    ESTAVEL = "estavel"
    ALTA = "alta"
    DADOS_INSUFICIENTES = "dados_insuficientes"


class TendenciaVegetacaoArea(UUIDPrimaryKeyMixin, Base):
    """Snapshot mais recente da tendencia/comparacao sazonal de um indice de
    vegetacao para uma area produtiva (docs/specs/04) — sempre reescrito via
    upsert por (area_produtiva_id, tipo), nunca historizado."""

    __tablename__ = "tendencia_vegetacao_area"
    __table_args__ = (
        UniqueConstraint("area_produtiva_id", "tipo", name="uq_tendencia_vegetacao_area_tipo"),
    )

    area_produtiva_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("area_produtiva.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[TipoIndiceVegetacao] = mapped_column(
        Enum(TipoIndiceVegetacao, name="tipo_indice_vegetacao"), nullable=False
    )
    janela_dias: Mapped[int] = mapped_column(Integer, nullable=False)
    periodo_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    periodo_fim: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valor_medio_periodo: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    inclinacao_diaria: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    variacao_pct_periodo: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    classificacao: Mapped[ClassificacaoTendencia] = mapped_column(
        Enum(ClassificacaoTendencia, name="classificacao_tendencia"), nullable=False
    )
    amostras_periodo: Mapped[int] = mapped_column(Integer, nullable=False)
    comparacao_sazonal_disponivel: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    valor_medio_periodo_anterior: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    variacao_sazonal_pct: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    amostras_periodo_anterior: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calculado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    versao_algoritmo: Mapped[str] = mapped_column(String(50), nullable=False)
