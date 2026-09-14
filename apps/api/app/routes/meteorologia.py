import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analise_temporal.lacunas import detectar_lacunas
from app.core.config import get_settings
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
from app.schemas.analise_temporal import LacunaRead
from app.schemas.meteorologia import (
    EstacaoResumo,
    ObservacaoRead,
    ReavaliarRepresentatividadeResponse,
    RepresentatividadeVariavelRead,
)

router = APIRouter(prefix="/meteorologia", tags=["meteorologia"])


def _resolver_estacao_ids(
    db: Session, estacao_id: uuid.UUID | None, fazenda_id: uuid.UUID | None, variavel: VariavelMeteorologica | None
) -> list[uuid.UUID] | None:
    """Resolve `estacao_id`/`fazenda_id` para a lista de estacoes a consultar.

    Com `fazenda_id`, resolve internamente via `avaliacao_representatividade`
    (referencia + auxiliares) — o frontend nao precisa saber qual
    `estacao_id` usar. Retorna `None` quando a fazenda nao tem nenhuma
    estacao qualificada (chamador deve tratar como "sem dado", nao erro).
    """
    if fazenda_id is not None:
        query_estacoes = select(AvaliacaoRepresentatividade.estacao_id).where(
            AvaliacaoRepresentatividade.fazenda_id == fazenda_id
        )
        if variavel is not None:
            query_estacoes = query_estacoes.where(AvaliacaoRepresentatividade.variavel == variavel)
        estacao_ids = list(db.execute(query_estacoes).scalars().all())
        return estacao_ids or None
    return [estacao_id]


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

    estacao_ids = _resolver_estacao_ids(db, estacao_id, fazenda_id, variavel)
    if estacao_ids is None:
        return []

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


@router.get("/lacunas", response_model=list[LacunaRead])
def listar_lacunas(
    variavel: VariavelMeteorologica,
    estacao_id: uuid.UUID | None = None,
    fazenda_id: uuid.UUID | None = None,
    inicio: datetime | None = None,
    fim: datetime | None = None,
    db: Session = Depends(get_db),
) -> list[LacunaRead]:
    if (estacao_id is None) == (fazenda_id is None):
        raise HTTPException(status_code=422, detail="Informe exatamente um de estacao_id ou fazenda_id")

    estacao_ids = _resolver_estacao_ids(db, estacao_id, fazenda_id, variavel)
    if estacao_ids is None:
        return []

    query = select(ObservacaoMeteorologica.timestamp).where(
        ObservacaoMeteorologica.estacao_id.in_(estacao_ids),
        ObservacaoMeteorologica.variavel == variavel,
    )
    if inicio is not None:
        query = query.where(ObservacaoMeteorologica.timestamp >= inicio)
    if fim is not None:
        query = query.where(ObservacaoMeteorologica.timestamp <= fim)

    datas_validas = [linha.date() for linha in db.execute(query).scalars().all()]
    fim_referencia = fim.date() if fim is not None else datetime.now().date()

    settings = get_settings()
    lacunas = detectar_lacunas(
        datas_validas, limiar_dias=settings.meteorologia_limiar_gap_dias, fim_referencia=fim_referencia
    )
    return [
        LacunaRead(periodo_inicio=lacuna.periodo_inicio, periodo_fim=lacuna.periodo_fim, dias=lacuna.dias)
        for lacuna in lacunas
    ]
