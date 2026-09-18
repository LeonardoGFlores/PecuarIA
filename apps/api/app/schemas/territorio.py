import uuid
from typing import Any

from geojson_pydantic import Polygon
from pydantic import BaseModel

from app.models.mixins import QualidadeEvidencia, StatusEvidencia
from app.models.territorio import SistemaProdutivo, TipoUso


class FazendaCreate(BaseModel):
    nome: str
    proprietario: str | None = None
    geom: Polygon
    area_total_ha: float | None = None
    fonte: str = "declarado_produtor"
    status: StatusEvidencia = StatusEvidencia.DECLARADO
    qualidade: QualidadeEvidencia = QualidadeEvidencia.MEDIA


class FazendaRead(BaseModel):
    id: uuid.UUID
    nome: str
    proprietario: str | None
    geom: dict[str, Any]
    area_total_ha: float | None
    versao: int
    fonte: str
    status: StatusEvidencia
    qualidade: QualidadeEvidencia


class AreaProdutivaCreate(BaseModel):
    nome: str
    geom: Polygon
    tipo_uso: TipoUso
    area_ha: float | None = None
    area_utilizavel_ha: float | None = None
    sistema_produtivo: SistemaProdutivo = SistemaProdutivo.NAO_DEFINIDO
    fonte: str = "declarado_produtor"
    status: StatusEvidencia = StatusEvidencia.DECLARADO
    qualidade: QualidadeEvidencia = QualidadeEvidencia.MEDIA


class AreaProdutivaRead(BaseModel):
    id: uuid.UUID
    fazenda_id: uuid.UUID
    nome: str
    geom: dict[str, Any]
    tipo_uso: TipoUso
    area_ha: float | None
    area_utilizavel_ha: float | None
    sistema_produtivo: SistemaProdutivo
    fonte: str
    status: StatusEvidencia
    qualidade: QualidadeEvidencia
