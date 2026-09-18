import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.geo import geojson_to_geom, geom_to_geojson
from app.models.meteorologia import EstacaoMeteorologica
from app.models.oferta import Fornecedor, LogisticaOferta, OfertaRegional
from app.schemas.fontes import (
    EstacaoMeteorologicaCreate,
    EstacaoMeteorologicaRead,
    FornecedorCreate,
    FornecedorRead,
    LogisticaOfertaCreate,
    LogisticaOfertaRead,
    OfertaRegionalCreate,
    OfertaRegionalRead,
)

router = APIRouter(prefix="/fontes", tags=["catalogo-de-fontes"])


def _oferta_to_read(oferta: OfertaRegional) -> OfertaRegionalRead:
    vencida = oferta.validade_cotacao is not None and oferta.validade_cotacao < datetime.now(timezone.utc)
    return OfertaRegionalRead(
        id=oferta.id,
        fornecedor_id=oferta.fornecedor_id,
        categoria=oferta.categoria,
        especificacao=oferta.especificacao,
        unidade=oferta.unidade,
        quantidade_disponivel=oferta.quantidade_disponivel,
        quantidade_minima=oferta.quantidade_minima,
        preco=oferta.preco,
        condicoes=oferta.condicoes,
        sazonalidade=oferta.sazonalidade,
        data_registro=oferta.data_registro,
        validade_cotacao=oferta.validade_cotacao,
        fonte=oferta.fonte,
        vencida=vencida,
    )


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
        fonte=payload.fonte,
    )
    db.add(fornecedor)
    db.commit()
    db.refresh(fornecedor)
    return FornecedorRead.model_validate(fornecedor, from_attributes=True)


@router.get("/fornecedores/{fornecedor_id}", response_model=FornecedorRead)
def obter_fornecedor(fornecedor_id: uuid.UUID, db: Session = Depends(get_db)) -> FornecedorRead:
    fornecedor = db.get(Fornecedor, fornecedor_id)
    if fornecedor is None:
        raise HTTPException(status_code=404, detail="Fornecedor nao encontrado")
    return FornecedorRead.model_validate(fornecedor, from_attributes=True)


@router.put("/fornecedores/{fornecedor_id}", response_model=FornecedorRead)
def atualizar_fornecedor(
    fornecedor_id: uuid.UUID, payload: FornecedorCreate, db: Session = Depends(get_db)
) -> FornecedorRead:
    fornecedor = db.get(Fornecedor, fornecedor_id)
    if fornecedor is None:
        raise HTTPException(status_code=404, detail="Fornecedor nao encontrado")

    fornecedor.nome = payload.nome
    fornecedor.tipo = payload.tipo
    fornecedor.regiao = payload.regiao
    fornecedor.contato = payload.contato
    fornecedor.fonte = payload.fonte
    db.commit()
    db.refresh(fornecedor)
    return FornecedorRead.model_validate(fornecedor, from_attributes=True)


@router.delete("/fornecedores/{fornecedor_id}", status_code=204)
def remover_fornecedor(fornecedor_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    fornecedor = db.get(Fornecedor, fornecedor_id)
    if fornecedor is None:
        raise HTTPException(status_code=404, detail="Fornecedor nao encontrado")
    # Cascata intencional: sem o fornecedor, suas ofertas e a logistica de
    # cada uma nao tem mais sentido proprio (ver docs/specs/05).
    db.delete(fornecedor)
    db.commit()


@router.get("/ofertas", response_model=list[OfertaRegionalRead])
def listar_ofertas(fornecedor_id: uuid.UUID | None = None, db: Session = Depends(get_db)) -> list[OfertaRegionalRead]:
    query = select(OfertaRegional)
    if fornecedor_id is not None:
        query = query.where(OfertaRegional.fornecedor_id == fornecedor_id)
    ofertas = db.execute(query).scalars().all()
    return [_oferta_to_read(o) for o in ofertas]


@router.post("/ofertas", response_model=OfertaRegionalRead, status_code=201)
def criar_oferta(payload: OfertaRegionalCreate, db: Session = Depends(get_db)) -> OfertaRegionalRead:
    if db.get(Fornecedor, payload.fornecedor_id) is None:
        raise HTTPException(status_code=404, detail="Fornecedor nao encontrado")
    if (
        payload.quantidade_minima is not None
        and payload.quantidade_disponivel is not None
        and payload.quantidade_minima > payload.quantidade_disponivel
    ):
        raise HTTPException(status_code=422, detail="quantidade_minima nao pode ser maior que quantidade_disponivel")

    oferta = OfertaRegional(**payload.model_dump())
    db.add(oferta)
    db.commit()
    db.refresh(oferta)
    return _oferta_to_read(oferta)


@router.get("/ofertas/{oferta_id}", response_model=OfertaRegionalRead)
def obter_oferta(oferta_id: uuid.UUID, db: Session = Depends(get_db)) -> OfertaRegionalRead:
    oferta = db.get(OfertaRegional, oferta_id)
    if oferta is None:
        raise HTTPException(status_code=404, detail="Oferta nao encontrada")
    return _oferta_to_read(oferta)


@router.put("/ofertas/{oferta_id}", response_model=OfertaRegionalRead)
def atualizar_oferta(
    oferta_id: uuid.UUID, payload: OfertaRegionalCreate, db: Session = Depends(get_db)
) -> OfertaRegionalRead:
    oferta = db.get(OfertaRegional, oferta_id)
    if oferta is None:
        raise HTTPException(status_code=404, detail="Oferta nao encontrada")
    if db.get(Fornecedor, payload.fornecedor_id) is None:
        raise HTTPException(status_code=404, detail="Fornecedor nao encontrado")
    if (
        payload.quantidade_minima is not None
        and payload.quantidade_disponivel is not None
        and payload.quantidade_minima > payload.quantidade_disponivel
    ):
        raise HTTPException(status_code=422, detail="quantidade_minima nao pode ser maior que quantidade_disponivel")

    for campo, valor in payload.model_dump().items():
        setattr(oferta, campo, valor)
    db.commit()
    db.refresh(oferta)
    return _oferta_to_read(oferta)


@router.delete("/ofertas/{oferta_id}", status_code=204)
def remover_oferta(oferta_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    oferta = db.get(OfertaRegional, oferta_id)
    if oferta is None:
        raise HTTPException(status_code=404, detail="Oferta nao encontrada")
    db.delete(oferta)
    db.commit()


@router.get("/ofertas/{oferta_id}/logistica", response_model=list[LogisticaOfertaRead])
def listar_logistica(oferta_id: uuid.UUID, db: Session = Depends(get_db)) -> list[LogisticaOfertaRead]:
    if db.get(OfertaRegional, oferta_id) is None:
        raise HTTPException(status_code=404, detail="Oferta nao encontrada")
    logisticas = db.execute(select(LogisticaOferta).where(LogisticaOferta.oferta_id == oferta_id)).scalars().all()
    return [LogisticaOfertaRead.model_validate(l, from_attributes=True) for l in logisticas]


@router.post("/ofertas/{oferta_id}/logistica", response_model=LogisticaOfertaRead, status_code=201)
def criar_logistica(
    oferta_id: uuid.UUID, payload: LogisticaOfertaCreate, db: Session = Depends(get_db)
) -> LogisticaOfertaRead:
    if db.get(OfertaRegional, oferta_id) is None:
        raise HTTPException(status_code=404, detail="Oferta nao encontrada")

    logistica = LogisticaOferta(oferta_id=oferta_id, **payload.model_dump())
    db.add(logistica)
    db.commit()
    db.refresh(logistica)
    return LogisticaOfertaRead.model_validate(logistica, from_attributes=True)


@router.get("/logistica/{logistica_id}", response_model=LogisticaOfertaRead)
def obter_logistica(logistica_id: uuid.UUID, db: Session = Depends(get_db)) -> LogisticaOfertaRead:
    logistica = db.get(LogisticaOferta, logistica_id)
    if logistica is None:
        raise HTTPException(status_code=404, detail="Logistica nao encontrada")
    return LogisticaOfertaRead.model_validate(logistica, from_attributes=True)


@router.put("/logistica/{logistica_id}", response_model=LogisticaOfertaRead)
def atualizar_logistica(
    logistica_id: uuid.UUID, payload: LogisticaOfertaCreate, db: Session = Depends(get_db)
) -> LogisticaOfertaRead:
    logistica = db.get(LogisticaOferta, logistica_id)
    if logistica is None:
        raise HTTPException(status_code=404, detail="Logistica nao encontrada")

    for campo, valor in payload.model_dump().items():
        setattr(logistica, campo, valor)
    db.commit()
    db.refresh(logistica)
    return LogisticaOfertaRead.model_validate(logistica, from_attributes=True)


@router.delete("/logistica/{logistica_id}", status_code=204)
def remover_logistica(logistica_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    logistica = db.get(LogisticaOferta, logistica_id)
    if logistica is None:
        raise HTTPException(status_code=404, detail="Logistica nao encontrada")
    db.delete(logistica)
    db.commit()
