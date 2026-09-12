import enum
import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import UUIDPrimaryKeyMixin


class FonteCena(str, enum.Enum):
    SENTINEL2_L2A = "SENTINEL2_L2A"


class StatusProcessamentoCena(str, enum.Enum):
    PENDENTE = "pendente"
    PROCESSADA = "processada"
    REJEITADA = "rejeitada"


class TipoIndiceVegetacao(str, enum.Enum):
    NDVI = "NDVI"
    EVI = "EVI"


class CenaSatelite(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "cena_satelite"

    fonte: Mapped[FonteCena] = mapped_column(Enum(FonteCena, name="fonte_cena"), nullable=False)
    tile_id: Mapped[str] = mapped_column(String(60), nullable=False)
    data_aquisicao: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cobertura_nuvem_cena_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    geom: Mapped[str] = mapped_column(Geometry(geometry_type="POLYGON", srid=4326), nullable=False)
    status_processamento: Mapped[StatusProcessamentoCena] = mapped_column(
        Enum(StatusProcessamentoCena, name="status_processamento_cena"),
        nullable=False,
        default=StatusProcessamentoCena.PENDENTE,
    )

    indices: Mapped[list["IndiceVegetacaoArea"]] = relationship(
        back_populates="cena", cascade="all, delete-orphan"
    )


class IndiceVegetacaoArea(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "indice_vegetacao_area"

    area_produtiva_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("area_produtiva.id", ondelete="CASCADE"), nullable=False
    )
    cena_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cena_satelite.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[TipoIndiceVegetacao] = mapped_column(
        Enum(TipoIndiceVegetacao, name="tipo_indice_vegetacao"), nullable=False
    )
    data_aquisicao: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cobertura_valida_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    mediana: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    p10: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    p25: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    p75: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    p90: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    desvio_padrao: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    versao_processamento: Mapped[str] = mapped_column(String(50), nullable=False)
    raster_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)

    cena: Mapped["CenaSatelite"] = relationship(back_populates="indices")
