import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.tasks import enfileirar
from app.models.meteorologia import (
    AvaliacaoRepresentatividade,
    EstacaoMeteorologica,
    ObservacaoMeteorologica,
    PapelRepresentatividade,
    VariavelMeteorologica,
)
from app.models.territorio import Fazenda
from app.schemas.meteorologia import (
    EstacaoResumo,
    ObservacaoRead,
    ReavaliarRepresentatividadeResponse,
    RepresentatividadeVariavelRead,
)

router = APIRouter(prefix="/meteorologia", tags=["meteorologia"])


@router.get("/observacoes", response_model=list[ObservacaoRead])
def listar_observacoes(
    estacao_id: uuid.UUID | None = None,
    fazenda_id: uuid.UUID | None = None,
    variavel: VariavelMeteorologica | None = None,
    inicio: datetime | None = None,
    fim: datetime | None = None,
    db: Session = Depends(get_db),
) -> list[ObservacaoRead]:
    if (estacao_id is None) == (fazenda_id is None):
        raise HTTPException(status_code=422, detail="Informe exatamente um de estacao_id ou fazenda_id")

    if fazenda_id is not None:
        # Resolve internamente via avaliacao_representatividade (referencia +
        # auxiliares) — o frontend nao precisa saber qual estacao_id usar.
        query_estacoes = select(AvaliacaoRepresentatividade.estacao_id).where(
            AvaliacaoRepresentatividade.fazenda_id == fazenda_id
        )
        if variavel is not None:
            query_estacoes = query_estacoes.where(AvaliacaoRepresentatividade.variavel == variavel)
        estacao_ids = list(db.execute(query_estacoes).scalars().all())
        if not estacao_ids:
            return []
    else:
        estacao_ids = [estacao_id]

    query = select(ObservacaoMeteorologica).where(ObservacaoMeteorologica.estacao_id.in_(estacao_ids))
    if variavel is not None:
        query = query.where(ObservacaoMeteorologica.variavel == variavel)
    if inicio is not None:
        query = query.where(ObservacaoMeteorologica.timestamp >= inicio)
    if fim is not None:
        query = query.where(ObservacaoMeteorologica.timestamp <= fim)
    query = query.order_by(ObservacaoMeteorologica.timestamp)

    observacoes = db.execute(query).scalars().all()
    return [ObservacaoRead.model_validate(o, from_attributes=True) for o in observacoes]


@router.get("/representatividade", response_model=list[RepresentatividadeVariavelRead])
def obter_representatividade(fazenda_id: uuid.UUID, db: Session = Depends(get_db)) -> list[RepresentatividadeVariavelRead]:
    linhas = db.execute(
        select(AvaliacaoRepresentatividade, EstacaoMeteorologica)
        .join(EstacaoMeteorologica, AvaliacaoRepresentatividade.estacao_id == EstacaoMeteorologica.id)
        .where(AvaliacaoRepresentatividade.fazenda_id == fazenda_id)
    ).all()

    por_variavel: dict[VariavelMeteorologica, dict] = {}
    for avaliacao, estacao in linhas:
        resumo = EstacaoResumo(
            id=estacao.id,
            nome=estacao.nome,
            fonte=estacao.fonte,
            tipo=estacao.tipo,
            distancia_km=float(avaliacao.distancia_km),
            criterio_completude=avaliacao.criterio_completude,
            criterio_atualizacao=avaliacao.criterio_atualizacao,
            criterio_consistencia=avaliacao.criterio_consistencia,
        )
        bucket = por_variavel.setdefault(avaliacao.variavel, {"referencia": None, "auxiliares": []})
        if avaliacao.papel == PapelRepresentatividade.REFERENCIA:
            bucket["referencia"] = resumo
        else:
            bucket["auxiliares"].append(resumo)

    return [
        RepresentatividadeVariavelRead(variavel=variavel, referencia=dados["referencia"], auxiliares=dados["auxiliares"])
        for variavel, dados in por_variavel.items()
    ]


@router.post(
    "/representatividade/{fazenda_id}/reavaliar",
    response_model=ReavaliarRepresentatividadeResponse,
    status_code=202,
)
def reavaliar_representatividade(fazenda_id: uuid.UUID, db: Session = Depends(get_db)) -> ReavaliarRepresentatividadeResponse:
    if db.get(Fazenda, fazenda_id) is None:
        raise HTTPException(status_code=404, detail="Fazenda nao encontrada")
    enfileirar("qualidade.avaliar_fazenda", str(fazenda_id))
    return ReavaliarRepresentatividadeResponse(mensagem="Reavaliacao de representatividade enfileirada")
