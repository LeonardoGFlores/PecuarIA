import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.geo import geojson_to_geom, geom_to_geojson
from app.models.territorio import AreaProdutiva, Fazenda
from app.schemas.territorio import (
    AreaProdutivaCreate,
    AreaProdutivaRead,
    FazendaCreate,
    FazendaRead,
)

router = APIRouter(tags=["territorio"])


def _fazenda_to_read(fazenda: Fazenda) -> FazendaRead:
    return FazendaRead(
        id=fazenda.id,
        nome=fazenda.nome,
        proprietario=fazenda.proprietario,
        geom=geom_to_geojson(fazenda.geom),
        area_total_ha=fazenda.area_total_ha,
        versao=fazenda.versao,
        fonte=fazenda.fonte,
        status=fazenda.status,
        qualidade=fazenda.qualidade,
    )


def _area_to_read(area: AreaProdutiva) -> AreaProdutivaRead:
    return AreaProdutivaRead(
        id=area.id,
        fazenda_id=area.fazenda_id,
        nome=area.nome,
        geom=geom_to_geojson(area.geom),
        tipo_uso=area.tipo_uso,
        area_ha=area.area_ha,
        area_utilizavel_ha=area.area_utilizavel_ha,
        sistema_produtivo=area.sistema_produtivo,
        fonte=area.fonte,
        status=area.status,
        qualidade=area.qualidade,
    )


@router.get("/fazendas", response_model=list[FazendaRead])
def listar_fazendas(db: Session = Depends(get_db)) -> list[FazendaRead]:
    fazendas = db.execute(select(Fazenda)).scalars().all()
    return [_fazenda_to_read(f) for f in fazendas]


@router.post("/fazendas", response_model=FazendaRead, status_code=201)
def criar_fazenda(payload: FazendaCreate, db: Session = Depends(get_db)) -> FazendaRead:
    fazenda = Fazenda(
        nome=payload.nome,
        proprietario=payload.proprietario,
        geom=geojson_to_geom(payload.geom.model_dump()),
        area_total_ha=payload.area_total_ha,
        fonte=payload.fonte,
        status=payload.status,
        qualidade=payload.qualidade,
    )
    db.add(fazenda)
    db.commit()
    db.refresh(fazenda)
    return _fazenda_to_read(fazenda)


@router.get("/fazendas/{fazenda_id}", response_model=FazendaRead)
def obter_fazenda(fazenda_id: uuid.UUID, db: Session = Depends(get_db)) -> FazendaRead:
    fazenda = db.get(Fazenda, fazenda_id)
    if fazenda is None:
        raise HTTPException(status_code=404, detail="Fazenda nao encontrada")
    return _fazenda_to_read(fazenda)


@router.get("/fazendas/{fazenda_id}/areas-produtivas", response_model=list[AreaProdutivaRead])
def listar_areas_produtivas(fazenda_id: uuid.UUID, db: Session = Depends(get_db)) -> list[AreaProdutivaRead]:
    if db.get(Fazenda, fazenda_id) is None:
        raise HTTPException(status_code=404, detail="Fazenda nao encontrada")
    areas = db.execute(select(AreaProdutiva).where(AreaProdutiva.fazenda_id == fazenda_id)).scalars().all()
    return [_area_to_read(a) for a in areas]


@router.post(
    "/fazendas/{fazenda_id}/areas-produtivas",
    response_model=AreaProdutivaRead,
    status_code=201,
)
def criar_area_produtiva(
    fazenda_id: uuid.UUID, payload: AreaProdutivaCreate, db: Session = Depends(get_db)
) -> AreaProdutivaRead:
    if db.get(Fazenda, fazenda_id) is None:
        raise HTTPException(status_code=404, detail="Fazenda nao encontrada")

    if (
        payload.area_utilizavel_ha is not None
        and payload.area_ha is not None
        and payload.area_utilizavel_ha > payload.area_ha
    ):
        raise HTTPException(
            status_code=422, detail="area_utilizavel_ha nao pode ser maior que area_ha"
        )

    area = AreaProdutiva(
        fazenda_id=fazenda_id,
        nome=payload.nome,
        geom=geojson_to_geom(payload.geom.model_dump()),
        tipo_uso=payload.tipo_uso,
        area_ha=payload.area_ha,
        area_utilizavel_ha=payload.area_utilizavel_ha,
        sistema_produtivo=payload.sistema_produtivo,
        fonte=payload.fonte,
        status=payload.status,
        qualidade=payload.qualidade,
    )
    db.add(area)
    db.commit()
    db.refresh(area)
    return _area_to_read(area)
