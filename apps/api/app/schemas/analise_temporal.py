import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.analise_temporal import ClassificacaoTendencia
from app.models.vegetacao import TipoIndiceVegetacao


class TendenciaVegetacaoRead(BaseModel):
    id: uuid.UUID
    area_produtiva_id: uuid.UUID
    tipo: TipoIndiceVegetacao
    janela_dias: int
    periodo_inicio: datetime
    periodo_fim: datetime
    valor_medio_periodo: float | None
    inclinacao_diaria: float | None
    variacao_pct_periodo: float | None
    classificacao: ClassificacaoTendencia
    amostras_periodo: int
    comparacao_sazonal_disponivel: bool
    valor_medio_periodo_anterior: float | None
    variacao_sazonal_pct: float | None
    amostras_periodo_anterior: int | None
    calculado_em: datetime
    versao_algoritmo: str


class LacunaRead(BaseModel):
    periodo_inicio: date
    periodo_fim: date
    dias: int


class RecalcularTendenciaResponse(BaseModel):
    mensagem: str
