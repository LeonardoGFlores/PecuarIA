import uuid
from datetime import datetime
from typing import Any

from geojson_pydantic import Point
from pydantic import BaseModel

from app.models.meteorologia import FonteEstacao, TipoEstacao
from app.models.oferta import TipoFornecedor


class EstacaoMeteorologicaCreate(BaseModel):
    fonte: FonteEstacao
    codigo_externo: str | None = None
    nome: str
    geom: Point
    altitude_m: float | None = None
    operador: str | None = None
    tipo: TipoEstacao
    variaveis_disponiveis: list[str] = []
    periodo_inicio_serie: datetime | None = None
    periodo_fim_serie: datetime | None = None


class EstacaoMeteorologicaRead(BaseModel):
    id: uuid.UUID
    fonte: FonteEstacao
    codigo_externo: str | None
    nome: str
    geom: dict[str, Any]
    altitude_m: float | None
    operador: str | None
    tipo: TipoEstacao
    variaveis_disponiveis: list[str]
    periodo_inicio_serie: datetime | None
    periodo_fim_serie: datetime | None


class FornecedorCreate(BaseModel):
    nome: str
    tipo: TipoFornecedor
    regiao: str | None = None
    contato: str | None = None


class FornecedorRead(BaseModel):
    id: uuid.UUID
    nome: str
    tipo: TipoFornecedor
    regiao: str | None
    contato: str | None
