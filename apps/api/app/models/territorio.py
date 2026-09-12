import enum
import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import ProvenanceMixin, UUIDPrimaryKeyMixin


class TipoUso(str, enum.Enum):
    PASTO = "pasto"
    MATA = "mata"
    AGUA = "agua"
    LAVOURA = "lavoura"
    INFRAESTRUTURA = "infraestrutura"
    OUTRO = "outro"


class SistemaProdutivo(str, enum.Enum):
    CORTE = "corte"
    LEITE = "leite"
    AGRICULTURA = "agricultura"
    MISTO = "misto"
    NAO_DEFINIDO = "nao_definido"


class TipoInfraestrutura(str, enum.Enum):
    AGUA = "agua"
    CURRAL = "curral"
    CERCA = "cerca"
    GALPAO = "galpao"
    ACESSO = "acesso"
    OUTRO = "outro"


class Fazenda(UUIDPrimaryKeyMixin, ProvenanceMixin, Base):
    __tablename__ = "fazenda"

    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    proprietario: Mapped[str | None] = mapped_column(String(200), nullable=True)
    geom: Mapped[str] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326), nullable=False
    )
    area_total_ha: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    versao: Mapped[int] = mapped_column(default=1, nullable=False)

    areas_produtivas: Mapped[list["AreaProdutiva"]] = relationship(
        back_populates="fazenda", cascade="all, delete-orphan"
    )
    pontos_infraestrutura: Mapped[list["PontoInfraestrutura"]] = relationship(
        back_populates="fazenda", cascade="all, delete-orphan"
    )


class AreaProdutiva(UUIDPrimaryKeyMixin, ProvenanceMixin, Base):
    __tablename__ = "area_produtiva"

    fazenda_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fazenda.id", ondelete="CASCADE"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    geom: Mapped[str] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326), nullable=False
    )
    tipo_uso: Mapped[TipoUso] = mapped_column(Enum(TipoUso, name="tipo_uso"), nullable=False)
    area_ha: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    area_utilizavel_ha: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    sistema_produtivo: Mapped[SistemaProdutivo] = mapped_column(
        Enum(SistemaProdutivo, name="sistema_produtivo"),
        nullable=False,
        default=SistemaProdutivo.NAO_DEFINIDO,
    )

    fazenda: Mapped["Fazenda"] = relationship(back_populates="areas_produtivas")
    historico_uso: Mapped[list["HistoricoUsoArea"]] = relationship(
        back_populates="area_produtiva", cascade="all, delete-orphan"
    )


class HistoricoUsoArea(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "historico_uso_area"

    area_produtiva_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("area_produtiva.id", ondelete="CASCADE"), nullable=False
    )
    uso: Mapped[TipoUso] = mapped_column(Enum(TipoUso, name="tipo_uso"), nullable=False)
    vigencia_inicio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    vigencia_fim: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    declarado_por: Mapped[str | None] = mapped_column(String(200), nullable=True)
    fonte: Mapped[str] = mapped_column(String(120), nullable=False)

    area_produtiva: Mapped["AreaProdutiva"] = relationship(back_populates="historico_uso")


class PontoInfraestrutura(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ponto_infraestrutura"

    fazenda_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fazenda.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[TipoInfraestrutura] = mapped_column(
        Enum(TipoInfraestrutura, name="tipo_infraestrutura"), nullable=False
    )
    geom: Mapped[str] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326), nullable=False
    )
    atributos: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    fazenda: Mapped["Fazenda"] = relationship(back_populates="pontos_infraestrutura")
