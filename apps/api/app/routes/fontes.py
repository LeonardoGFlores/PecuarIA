from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.geo import geojson_to_geom, geom_to_geojson
from app.models.meteorologia import EstacaoMeteorologica
from app.models.oferta import Fornecedor
from app.schemas.fontes import (
    EstacaoMeteorologicaCreate,
    EstacaoMeteorologicaRead,
    FornecedorCreate,
    FornecedorRead,
)

router = APIRouter(prefix="/fontes", tags=["catalogo-de-fontes"])


def _estacao_to_read(estacao: EstacaoMeteorologica) -> EstacaoMeteorologicaRead:
    return EstacaoMeteorologicaRead(
        id=estacao.id,
        fonte=estacao.fonte,
        codigo_externo=estacao.codigo_externo,
        nome=estacao.nome,
        geom=geom_to_geojson(estacao.geom),
        altitude_m=estacao.altitude_m,
        operador=estacao.operador,
        tipo=estacao.tipo,
        variaveis_disponiveis=estacao.variaveis_disponiveis,
        periodo_inicio_serie=estacao.periodo_inicio_serie,
        periodo_fim_serie=estacao.periodo_fim_serie,
    )


@router.get("/estacoes-meteorologicas", response_model=list[EstacaoMeteorologicaRead])
def listar_estacoes(db: Session = Depends(get_db)) -> list[EstacaoMeteorologicaRead]:
    estacoes = db.execute(select(EstacaoMeteorologica)).scalars().all()
    return [_estacao_to_read(e) for e in estacoes]


@router.post("/estacoes-meteorologicas", response_model=EstacaoMeteorologicaRead, status_code=201)
def criar_estacao(payload: EstacaoMeteorologicaCreate, db: Session = Depends(get_db)) -> EstacaoMeteorologicaRead:
    estacao = EstacaoMeteorologica(
        fonte=payload.fonte,
        codigo_externo=payload.codigo_externo,
        nome=payload.nome,
        geom=geojson_to_geom(payload.geom.model_dump()),
        altitude_m=payload.altitude_m,
        operador=payload.operador,
        tipo=payload.tipo,
        variaveis_disponiveis=payload.variaveis_disponiveis,
        periodo_inicio_serie=payload.periodo_inicio_serie,
        periodo_fim_serie=payload.periodo_fim_serie,
    )
    db.add(estacao)
    db.commit()
    db.refresh(estacao)
    return _estacao_to_read(estacao)


@router.get("/fornecedores", response_model=list[FornecedorRead])
def listar_fornecedores(db: Session = Depends(get_db)) -> list[FornecedorRead]:
    fornecedores = db.execute(select(Fornecedor)).scalars().all()
    return [FornecedorRead.model_validate(f, from_attributes=True) for f in fornecedores]


@router.post("/fornecedores", response_model=FornecedorRead, status_code=201)
def criar_fornecedor(payload: FornecedorCreate, db: Session = Depends(get_db)) -> FornecedorRead:
    fornecedor = Fornecedor(
        nome=payload.nome,
        tipo=payload.tipo,
        regiao=payload.regiao,
        contato=payload.contato,
    )
    db.add(fornecedor)
    db.commit()
    db.refresh(fornecedor)
    return FornecedorRead.model_validate(fornecedor, from_attributes=True)
