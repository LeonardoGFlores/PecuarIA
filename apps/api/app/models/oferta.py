import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import UUIDPrimaryKeyMixin


class TipoFornecedor(str, enum.Enum):
    ANIMAIS = "animais"
    INSUMOS = "insumos"
    SERVICOS = "servicos"
    FRETE = "frete"
    COMPRADOR = "comprador"


class Fornecedor(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "fornecedor"

    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo: Mapped[TipoFornecedor] = mapped_column(Enum(TipoFornecedor, name="tipo_fornecedor"), nullable=False)
    regiao: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contato: Mapped[str | None] = mapped_column(String(200), nullable=True)

    ofertas: Mapped[list["OfertaRegional"]] = relationship(
        back_populates="fornecedor", cascade="all, delete-orphan"
    )


class OfertaRegional(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "oferta_regional"

    fornecedor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fornecedor.id", ondelete="CASCADE"), nullable=False
    )
    categoria: Mapped[str] = mapped_column(String(120), nullable=False)
    especificacao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    unidade: Mapped[str] = mapped_column(String(30), nullable=False)
    quantidade_disponivel: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    quantidade_minima: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    preco: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    condicoes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sazonalidade: Mapped[str | None] = mapped_column(String(200), nullable=True)
    data_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    validade_cotacao: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fonte: Mapped[str] = mapped_column(String(120), nullable=False)

    fornecedor: Mapped["Fornecedor"] = relationship(back_populates="ofertas")
    logistica: Mapped[list["LogisticaOferta"]] = relationship(
        back_populates="oferta", cascade="all, delete-orphan"
    )


class LogisticaOferta(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "logistica_oferta"

    oferta_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("oferta_regional.id", ondelete="CASCADE"), nullable=False
    )
    distancia_km: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    prazo_entrega_dias: Mapped[int | None] = mapped_column(nullable=True)
    custo_frete: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)

    oferta: Mapped["OfertaRegional"] = relationship(back_populates="logistica")
