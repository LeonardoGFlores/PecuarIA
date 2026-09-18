import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import UUIDPrimaryKeyMixin


class ToleranciaRisco(str, enum.Enum):
    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"


class ApoioTecnico(str, enum.Enum):
    PROPRIO = "proprio"
    CONTRATADO = "contratado"
    NENHUM = "nenhum"


class PerfilProdutor(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "perfil_produtor"
    __table_args__ = (UniqueConstraint("fazenda_id", name="uq_perfil_produtor_fazenda_id"),)

    fazenda_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fazenda.id", ondelete="CASCADE"), nullable=False
    )
    objetivos: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    capital_disponivel: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    limite_investimento: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    capital_giro: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    tolerancia_risco: Mapped[ToleranciaRisco] = mapped_column(
        Enum(ToleranciaRisco, name="tolerancia_risco"), nullable=False, default=ToleranciaRisco.MEDIA
    )
    disponibilidade_gestao_horas_semana: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)


class Equipe(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "equipe"
    __table_args__ = (UniqueConstraint("fazenda_id", name="uq_equipe_fazenda_id"),)

    fazenda_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fazenda.id", ondelete="CASCADE"), nullable=False
    )
    quantidade_pessoas: Mapped[int] = mapped_column(nullable=False, default=0)
    funcoes: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    disponibilidade_sazonal: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    competencias: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    apoio_tecnico: Mapped[ApoioTecnico] = mapped_column(
        Enum(ApoioTecnico, name="apoio_tecnico"), nullable=False, default=ApoioTecnico.NENHUM
    )
