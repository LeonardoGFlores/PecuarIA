import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class StatusEvidencia(str, enum.Enum):
    OBSERVADO = "observado"
    DERIVADO = "derivado"
    ESTIMADO = "estimado"
    DECLARADO = "declarado"
    HIPOTESE = "hipotese"


class QualidadeEvidencia(str, enum.Enum):
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"
    INSUFICIENTE = "insuficiente"


class UUIDPrimaryKeyMixin:
    """Chave primaria UUID, padrao em todas as tabelas do dominio."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class ProvenanceMixin:
    """Metadados de proveniencia exigidos pelo contrato de dados (docs/specs/01).

    Toda tabela de evidencia carrega fonte, classificacao de status, qualidade,
    data de obtencao e versao de processamento. `unidade` e o periodo coberto
    sao opcionais pois nem toda entidade representa uma medida com unidade ou
    uma janela de tempo (ex.: cadastro de fazenda).
    """

    fonte: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[StatusEvidencia] = mapped_column(
        Enum(StatusEvidencia, name="status_evidencia"), nullable=False
    )
    qualidade: Mapped[QualidadeEvidencia] = mapped_column(
        Enum(QualidadeEvidencia, name="qualidade_evidencia"),
        nullable=False,
        default=QualidadeEvidencia.MEDIA,
    )
    data_obtencao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    versao_processamento: Mapped[str | None] = mapped_column(String(50), nullable=True)
    unidade: Mapped[str | None] = mapped_column(String(30), nullable=True)
    periodo_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    periodo_fim: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
