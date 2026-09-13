import enum
import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Enum, Float, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import StatusEvidencia, UUIDPrimaryKeyMixin


class FonteEstacao(str, enum.Enum):
    INMET = "INMET"
    NASA_POWER = "NASA_POWER"
    OUTRA = "outra"


class TipoEstacao(str, enum.Enum):
    OBSERVADO = "observado"
    GRADE = "grade"


class VariavelMeteorologica(str, enum.Enum):
    PRECIPITACAO = "precipitacao"
    TEMPERATURA = "temperatura"
    UMIDADE_RELATIVA = "umidade_relativa"
    RADIACAO = "radiacao"
    VENTO = "vento"


class PapelRepresentatividade(str, enum.Enum):
    REFERENCIA = "referencia"
    AUXILIAR = "auxiliar"


class NivelCriterioRepresentatividade(str, enum.Enum):
    BOM = "bom"
    REGULAR = "regular"
    INSUFICIENTE = "insuficiente"


class EstacaoMeteorologica(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "estacao_meteorologica"

    fonte: Mapped[FonteEstacao] = mapped_column(Enum(FonteEstacao, name="fonte_estacao"), nullable=False)
    codigo_externo: Mapped[str | None] = mapped_column(String(60), nullable=True)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    geom: Mapped[str] = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    altitude_m: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    operador: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tipo: Mapped[TipoEstacao] = mapped_column(Enum(TipoEstacao, name="tipo_estacao"), nullable=False)
    variaveis_disponiveis: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    periodo_inicio_serie: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    periodo_fim_serie: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    observacoes: Mapped[list["ObservacaoMeteorologica"]] = relationship(
        back_populates="estacao", cascade="all, delete-orphan"
    )


class ObservacaoMeteorologica(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "observacao_meteorologica"
    __table_args__ = (
        UniqueConstraint("estacao_id", "variavel", "timestamp", name="uq_observacao_estacao_variavel_timestamp"),
    )

    estacao_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("estacao_meteorologica.id", ondelete="CASCADE"), nullable=False
    )
    variavel: Mapped[VariavelMeteorologica] = mapped_column(
        Enum(VariavelMeteorologica, name="variavel_meteorologica"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valor: Mapped[float] = mapped_column(Float, nullable=False)
    unidade: Mapped[str] = mapped_column(String(30), nullable=False)
    flag_qualidade: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[StatusEvidencia] = mapped_column(
        Enum(StatusEvidencia, name="status_evidencia"),
        nullable=False,
        # server_default usa o NOME do membro (maiusculo) porque e assim que
        # o tipo enum status_evidencia foi criado no Postgres na Fase 1
        # (SQLAlchemy usa Enum.name como label da coluna, nao Enum.value).
        server_default=StatusEvidencia.OBSERVADO.name,
    )
    versao_processamento: Mapped[str | None] = mapped_column(String(50), nullable=True)

    estacao: Mapped["EstacaoMeteorologica"] = relationship(back_populates="observacoes")


class AvaliacaoRepresentatividade(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "avaliacao_representatividade"
    __table_args__ = (
        UniqueConstraint("fazenda_id", "estacao_id", "variavel", name="uq_avaliacao_fazenda_estacao_variavel"),
    )

    fazenda_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fazenda.id", ondelete="CASCADE"), nullable=False
    )
    estacao_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("estacao_meteorologica.id", ondelete="CASCADE"), nullable=False
    )
    variavel: Mapped[VariavelMeteorologica] = mapped_column(
        Enum(VariavelMeteorologica, name="variavel_meteorologica"), nullable=False
    )
    distancia_km: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    criterio_completude: Mapped[NivelCriterioRepresentatividade] = mapped_column(
        Enum(NivelCriterioRepresentatividade, name="nivel_criterio_representatividade"), nullable=False
    )
    criterio_atualizacao: Mapped[NivelCriterioRepresentatividade] = mapped_column(
        Enum(NivelCriterioRepresentatividade, name="nivel_criterio_representatividade"), nullable=False
    )
    criterio_consistencia: Mapped[NivelCriterioRepresentatividade] = mapped_column(
        Enum(NivelCriterioRepresentatividade, name="nivel_criterio_representatividade"), nullable=False
    )
    papel: Mapped[PapelRepresentatividade] = mapped_column(
        Enum(PapelRepresentatividade, name="papel_representatividade"), nullable=False
    )
    calculado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    versao_algoritmo: Mapped[str | None] = mapped_column(String(50), nullable=True)
