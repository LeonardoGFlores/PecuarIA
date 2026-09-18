import uuid
from datetime import datetime
from typing import Any

from geojson_pydantic import Point
from pydantic import BaseModel, Field

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
    fonte: str = "declarado_produtor"


class FornecedorRead(BaseModel):
    id: uuid.UUID
    nome: str
    tipo: TipoFornecedor
    regiao: str | None
    contato: str | None
    fonte: str


class OfertaRegionalCreate(BaseModel):
    fornecedor_id: uuid.UUID
    categoria: str
    especificacao: str | None = None
    unidade: str
    quantidade_disponivel: float | None = Field(default=None, ge=0)
    quantidade_minima: float | None = Field(default=None, ge=0)
    preco: float | None = Field(default=None, ge=0)
    condicoes: str | None = None
    sazonalidade: str | None = None
    data_registro: datetime
    validade_cotacao: datetime | None = None
    fonte: str


class OfertaRegionalRead(BaseModel):
    id: uuid.UUID
    fornecedor_id: uuid.UUID
    categoria: str
    especificacao: str | None
    unidade: str
    quantidade_disponivel: float | None
    quantidade_minima: float | None
    preco: float | None
    condicoes: str | None
    sazonalidade: str | None
    data_registro: datetime
    validade_cotacao: datetime | None
    fonte: str
    # Calculado na leitura a partir do relogio atual, nunca persistido — mesmo
    # padrao do campo `redundante` em IndiceVegetacaoRead (Fase 3).
    vencida: bool


class LogisticaOfertaCreate(BaseModel):
    distancia_km: float | None = Field(default=None, ge=0)
    prazo_entrega_dias: int | None = Field(default=None, ge=0)
    custo_frete: float | None = Field(default=None, ge=0)


class LogisticaOfertaRead(BaseModel):
    id: uuid.UUID
    oferta_id: uuid.UUID
    distancia_km: float | None
    prazo_entrega_dias: int | None
    custo_frete: float | None
