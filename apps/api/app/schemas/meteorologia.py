import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.meteorologia import (
    FonteEstacao,
    NivelCriterioRepresentatividade,
    PapelRepresentatividade,
    TipoEstacao,
    VariavelMeteorologica,
)
from app.models.mixins import StatusEvidencia


class ObservacaoRead(BaseModel):
    id: uuid.UUID
    estacao_id: uuid.UUID
    variavel: VariavelMeteorologica
    timestamp: datetime
    valor: float
    unidade: str
    flag_qualidade: str | None
    status: StatusEvidencia
    versao_processamento: str | None


class EstacaoResumo(BaseModel):
    id: uuid.UUID
    nome: str
    fonte: FonteEstacao
    tipo: TipoEstacao
    distancia_km: float
    criterio_completude: NivelCriterioRepresentatividade
    criterio_atualizacao: NivelCriterioRepresentatividade
    criterio_consistencia: NivelCriterioRepresentatividade


class RepresentatividadeVariavelRead(BaseModel):
    variavel: VariavelMeteorologica
    referencia: EstacaoResumo | None
    auxiliares: list[EstacaoResumo]


class ReavaliarRepresentatividadeResponse(BaseModel):
    mensagem: str
