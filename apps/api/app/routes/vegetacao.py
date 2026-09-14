import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analise_temporal.lacunas import detectar_lacunas
from app.core.config import get_settings
from app.core.db import get_db
from app.core.tasks import enfileirar
from app.models.analise_temporal import TendenciaVegetacaoArea
from app.models.territorio import AreaProdutiva, Fazenda
from app.models.vegetacao import (
    CenaSatelite,
    IndiceVegetacaoArea,
    QualidadeIndiceVegetacao,
    StatusProcessamentoCena,
    TipoIndiceVegetacao,
)
from app.schemas.analise_temporal import LacunaRead, RecalcularTendenciaResponse, TendenciaVegetacaoRead
from app.schemas.vegetacao import CenaSateliteRead, IndiceVegetacaoRead

router = APIRouter(prefix="/vegetacao", tags=["vegetacao"])


@router.get("/indices", response_model=list[IndiceVegetacaoRead])
def listar_indices(
    area_produtiva_id: uuid.UUID,
    tipo: TipoIndiceVegetacao | None = None,
    inicio: datetime | None = None,
    fim: datetime | None = None,
    db: Session = Depends(get_db),
) -> list[IndiceVegetacaoRead]:
    if db.get(AreaProdutiva, area_produtiva_id) is None:
        raise HTTPException(status_code=404, detail="Area produtiva nao encontrada")

    query = (
        select(IndiceVegetacaoArea, CenaSatelite.status_processamento)
        .join(CenaSatelite, IndiceVegetacaoArea.cena_id == CenaSatelite.id)
        .where(IndiceVegetacaoArea.area_produtiva_id == area_produtiva_id)
    )
    if tipo is not None:
        query = query.where(IndiceVegetacaoArea.tipo == tipo)
    if inicio is not None:
        query = query.where(IndiceVegetacaoArea.data_aquisicao >= inicio)
    if fim is not None:
        query = query.where(IndiceVegetacaoArea.data_aquisicao <= fim)
    query = query.order_by(IndiceVegetacaoArea.data_aquisicao)

    linhas = db.execute(query).all()
    return [
        IndiceVegetacaoRead(
            id=indice.id,
            area_produtiva_id=indice.area_produtiva_id,
            cena_id=indice.cena_id,
            tipo=indice.tipo,
            data_aquisicao=indice.data_aquisicao,
            cobertura_valida_pct=indice.cobertura_valida_pct,
            mediana=indice.mediana,
            p10=indice.p10,
            p25=indice.p25,
            p75=indice.p75,
            p90=indice.p90,
            desvio_padrao=indice.desvio_padrao,
            qualidade=indice.qualidade,
            versao_processamento=indice.versao_processamento,
            raster_ref=indice.raster_ref,
            redundante=status_cena == StatusProcessamentoCena.REDUNDANTE,
        )
        for indice, status_cena in linhas
    ]


@router.get("/cenas", response_model=list[CenaSateliteRead])
def listar_cenas(
    fazenda_id: uuid.UUID,
    inicio: datetime | None = None,
    fim: datetime | None = None,
    db: Session = Depends(get_db),
) -> list[CenaSateliteRead]:
    if db.get(Fazenda, fazenda_id) is None:
        raise HTTPException(status_code=404, detail="Fazenda nao encontrada")

    # Cenas nao tem fazenda_id proprio (uma cena de ~100x100km e compartilhada
    # entre fazendas vizinhas) — o vinculo e sempre espacial. Inclui
    # rejeitadas/redundantes (nunca apagadas) para a tela de Historico
    # ambiental poder mostrar lacunas e o porque.
    query = select(CenaSatelite).join(Fazenda, func.ST_Intersects(CenaSatelite.geom, Fazenda.geom)).where(
        Fazenda.id == fazenda_id
    )
    if inicio is not None:
        query = query.where(CenaSatelite.data_aquisicao >= inicio)
    if fim is not None:
        query = query.where(CenaSatelite.data_aquisicao <= fim)
    query = query.order_by(CenaSatelite.data_aquisicao)

    cenas = db.execute(query).scalars().all()
    return [
        CenaSateliteRead(
            id=cena.id,
            fonte=cena.fonte,
            item_stac_id=cena.item_stac_id,
            tile_id=cena.tile_id,
            data_aquisicao=cena.data_aquisicao,
            cobertura_nuvem_cena_pct=cena.cobertura_nuvem_cena_pct,
            status_processamento=cena.status_processamento,
        )
        for cena in cenas
    ]


@router.get("/tendencia", response_model=list[TendenciaVegetacaoRead])
def listar_tendencias(
    area_produtiva_id: uuid.UUID,
    tipo: TipoIndiceVegetacao | None = None,
    db: Session = Depends(get_db),
) -> list[TendenciaVegetacaoRead]:
    if db.get(AreaProdutiva, area_produtiva_id) is None:
        raise HTTPException(status_code=404, detail="Area produtiva nao encontrada")

    query = select(TendenciaVegetacaoArea).where(TendenciaVegetacaoArea.area_produtiva_id == area_produtiva_id)
    if tipo is not None:
        query = query.where(TendenciaVegetacaoArea.tipo == tipo)

    tendencias = db.execute(query).scalars().all()
    return [TendenciaVegetacaoRead.model_validate(t, from_attributes=True) for t in tendencias]


@router.post(
    "/tendencia/{area_produtiva_id}/recalcular",
    response_model=RecalcularTendenciaResponse,
    status_code=202,
)
def recalcular_tendencia(area_produtiva_id: uuid.UUID, db: Session = Depends(get_db)) -> RecalcularTendenciaResponse:
    if db.get(AreaProdutiva, area_produtiva_id) is None:
        raise HTTPException(status_code=404, detail="Area produtiva nao encontrada")

    for tipo in (TipoIndiceVegetacao.NDVI, TipoIndiceVegetacao.EVI):
        enfileirar("analise_temporal.calcular_tendencia_area", str(area_produtiva_id), tipo.value)
    return RecalcularTendenciaResponse(mensagem="Recalculo de tendencia enfileirado")


@router.get("/lacunas", response_model=list[LacunaRead])
def listar_lacunas(
    area_produtiva_id: uuid.UUID,
    tipo: TipoIndiceVegetacao,
    inicio: datetime | None = None,
    fim: datetime | None = None,
    db: Session = Depends(get_db),
) -> list[LacunaRead]:
    if db.get(AreaProdutiva, area_produtiva_id) is None:
        raise HTTPException(status_code=404, detail="Area produtiva nao encontrada")

    query = select(IndiceVegetacaoArea.data_aquisicao).where(
        IndiceVegetacaoArea.area_produtiva_id == area_produtiva_id,
        IndiceVegetacaoArea.tipo == tipo,
        IndiceVegetacaoArea.qualidade == QualidadeIndiceVegetacao.SUFICIENTE,
    )
    if inicio is not None:
        query = query.where(IndiceVegetacaoArea.data_aquisicao >= inicio)
    if fim is not None:
        query = query.where(IndiceVegetacaoArea.data_aquisicao <= fim)

    datas_validas = [linha.date() for linha in db.execute(query).scalars().all()]
    fim_referencia = fim.date() if fim is not None else datetime.now().date()

    settings = get_settings()
    lacunas = detectar_lacunas(
        datas_validas, limiar_dias=settings.vegetacao_limiar_gap_dias, fim_referencia=fim_referencia
    )
    return [
        LacunaRead(periodo_inicio=lacuna.periodo_inicio, periodo_fim=lacuna.periodo_fim, dias=lacuna.dias)
        for lacuna in lacunas
    ]
