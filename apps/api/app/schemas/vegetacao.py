import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.vegetacao import (
    FonteCena,
    QualidadeIndiceVegetacao,
    StatusProcessamentoCena,
    TipoIndiceVegetacao,
)


class IndiceVegetacaoRead(BaseModel):
    id: uuid.UUID
    area_produtiva_id: uuid.UUID
    cena_id: uuid.UUID
    tipo: TipoIndiceVegetacao
    data_aquisicao: datetime
    cobertura_valida_pct: float
    mediana: float | None
    p10: float | None
    p25: float | None
    p75: float | None
    p90: float | None
    desvio_padrao: float | None
    qualidade: QualidadeIndiceVegetacao
    versao_processamento: str
    raster_ref: str | None
    # Derivado via join com cena_satelite.status_processamento — permite ao
    # frontend optar por mostrar so a leitura principal do dia ou tudo (a
    # linha redundante nunca e apagada, so deixa de ser a "principal").
    redundante: bool


class CenaSateliteRead(BaseModel):
    id: uuid.UUID
    fonte: FonteCena
    item_stac_id: str
    tile_id: str
    data_aquisicao: datetime
    cobertura_nuvem_cena_pct: float | None
    status_processamento: StatusProcessamentoCena
