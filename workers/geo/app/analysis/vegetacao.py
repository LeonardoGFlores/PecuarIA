"""Tasks Celery de tendencia de vegetacao (docs/specs/04): calcula a
tendencia recente e a comparacao sazonal de uma serie de
`indice_vegetacao_area` ja persistida (Fase 3) e grava o snapshot mais
recente em `tendencia_vegetacao_area`.

Disparo: encadeado ao fim de `ingestion/sentinel2.processar_cena_area`,
agendado semanalmente como rede de seguranca (a janela recente desliza no
tempo mesmo sem cena nova), e sob demanda via API.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app import db_enums
from app.analysis import tendencia
from app.config import get_settings
from app.db import get_engine, get_table
from app.ingestion.manifesto import rastrear_execucao
from app.tasks import celery_app
from app.versioning import VERSAO_ANALISE_TENDENCIA_VEGETACAO


class AreaNaoEncontradaError(RuntimeError):
    """A area produtiva referenciada por uma task de tendencia nao existe mais."""


def _buscar_serie(conn, area_produtiva_id: uuid.UUID, tipo: str, inicio: dt.datetime, fim: dt.datetime):
    """Amostras `(data_aquisicao, mediana)` de `indice_vegetacao_area` com
    `qualidade=SUFICIENTE` no intervalo [inicio, fim] — linhas
    `insuficiente` nunca entram na conta (contam como ausencia)."""
    tabela = get_table("indice_vegetacao_area")
    linhas = conn.execute(
        select(tabela.c.data_aquisicao, tabela.c.mediana).where(
            tabela.c.area_produtiva_id == area_produtiva_id,
            tabela.c.tipo == tipo,
            tabela.c.qualidade == db_enums.QUALIDADE_INDICE_SUFICIENTE,
            tabela.c.mediana.is_not(None),
            tabela.c.data_aquisicao >= inicio,
            tabela.c.data_aquisicao <= fim,
        )
    ).fetchall()
    return [(linha.data_aquisicao, float(linha.mediana)) for linha in linhas]


def _upsert_tendencia(
    conn,
    area_produtiva_id: uuid.UUID,
    tipo: str,
    resultado: tendencia.ResultadoTendencia,
    janela_dias: int,
    periodo_inicio: dt.datetime,
    periodo_fim: dt.datetime,
) -> None:
    tabela = get_table("tendencia_vegetacao_area")
    stmt = pg_insert(tabela).values(
        id=uuid.uuid4(),
        area_produtiva_id=area_produtiva_id,
        tipo=tipo,
        janela_dias=janela_dias,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        valor_medio_periodo=resultado.valor_medio_periodo,
        inclinacao_diaria=resultado.inclinacao_diaria,
        variacao_pct_periodo=resultado.variacao_pct_periodo,
        classificacao=resultado.classificacao,
        amostras_periodo=resultado.amostras_periodo,
        comparacao_sazonal_disponivel=resultado.comparacao_sazonal_disponivel,
        valor_medio_periodo_anterior=resultado.valor_medio_periodo_anterior,
        variacao_sazonal_pct=resultado.variacao_sazonal_pct,
        amostras_periodo_anterior=resultado.amostras_periodo_anterior,
        versao_algoritmo=VERSAO_ANALISE_TENDENCIA_VEGETACAO,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_tendencia_vegetacao_area_tipo",
        set_={
            "janela_dias": stmt.excluded.janela_dias,
            "periodo_inicio": stmt.excluded.periodo_inicio,
            "periodo_fim": stmt.excluded.periodo_fim,
            "valor_medio_periodo": stmt.excluded.valor_medio_periodo,
            "inclinacao_diaria": stmt.excluded.inclinacao_diaria,
            "variacao_pct_periodo": stmt.excluded.variacao_pct_periodo,
            "classificacao": stmt.excluded.classificacao,
            "amostras_periodo": stmt.excluded.amostras_periodo,
            "comparacao_sazonal_disponivel": stmt.excluded.comparacao_sazonal_disponivel,
            "valor_medio_periodo_anterior": stmt.excluded.valor_medio_periodo_anterior,
            "variacao_sazonal_pct": stmt.excluded.variacao_sazonal_pct,
            "amostras_periodo_anterior": stmt.excluded.amostras_periodo_anterior,
            "versao_algoritmo": stmt.excluded.versao_algoritmo,
            "calculado_em": func.now(),
        },
    )
    conn.execute(stmt)


@celery_app.task(name="analise_temporal.calcular_tendencia_area", queue="analise_temporal")
def calcular_tendencia_area(area_produtiva_id: str, tipo: str) -> dict:
    settings = get_settings()
    engine = get_engine()
    area_uuid = uuid.UUID(area_produtiva_id)

    agora = dt.datetime.now(dt.timezone.utc)
    periodo_inicio = agora - dt.timedelta(days=settings.tendencia_janela_dias)
    periodo_fim = agora

    tolerancia = dt.timedelta(days=settings.tendencia_janela_sazonal_tolerancia_dias)
    periodo_anterior_inicio = periodo_inicio - dt.timedelta(days=365) - tolerancia
    periodo_anterior_fim = periodo_fim - dt.timedelta(days=365) + tolerancia

    with engine.connect() as conn:
        area_tbl = get_table("area_produtiva")
        area_existe = conn.execute(select(area_tbl.c.id).where(area_tbl.c.id == area_uuid)).first()
        if area_existe is None:
            raise AreaNaoEncontradaError(
                f"area_produtiva {area_produtiva_id} nao encontrada — nao e possivel calcular tendencia"
            )

        with rastrear_execucao(
            conn,
            tipo=db_enums.TIPO_EXECUCAO_TENDENCIA_VEGETACAO,
            entrada_fontes=[f"indice_vegetacao_area:area={area_produtiva_id}:tipo={tipo}"],
            parametros={
                "area_produtiva_id": area_produtiva_id,
                "tipo": tipo,
                "janela_dias": settings.tendencia_janela_dias,
                "periodo_inicio": periodo_inicio.isoformat(),
                "periodo_fim": periodo_fim.isoformat(),
            },
            versao_pipeline=VERSAO_ANALISE_TENDENCIA_VEGETACAO,
        ) as (_execucao_id, resultado_manifesto):
            amostras = _buscar_serie(conn, area_uuid, tipo, periodo_inicio, periodo_fim)
            amostras_anteriores = _buscar_serie(conn, area_uuid, tipo, periodo_anterior_inicio, periodo_anterior_fim)

            resultado = tendencia.calcular_tendencia(
                amostras,
                amostras_anteriores,
                settings.tendencia_amostras_minimas,
                settings.tendencia_limiar_variacao_pct,
                settings.tendencia_amostras_minimas_sazonal,
            )

            _upsert_tendencia(
                conn, area_uuid, tipo, resultado, settings.tendencia_janela_dias, periodo_inicio, periodo_fim
            )
            resultado_manifesto["saida_referencias"].append(
                f"tendencia_vegetacao_area:area={area_produtiva_id}:tipo={tipo}:"
                f"classificacao={resultado.classificacao}"
            )
            conn.commit()

    return {
        "area_produtiva_id": area_produtiva_id,
        "tipo": tipo,
        "classificacao": resultado.classificacao,
        "amostras_periodo": resultado.amostras_periodo,
    }


@celery_app.task(name="analise_temporal.despachar_tendencias", queue="analise_temporal")
def despachar_tendencias() -> dict:
    """Redespacha `calcular_tendencia_area` para todo par (area_produtiva,
    tipo) — necessario porque a janela recente desliza no tempo mesmo sem
    cena nova (rede de seguranca semanal)."""
    engine = get_engine()
    with engine.connect() as conn:
        area_tbl = get_table("area_produtiva")
        areas = conn.execute(select(area_tbl.c.id)).fetchall()

    despachadas = 0
    for area in areas:
        for tipo in (db_enums.TIPO_INDICE_NDVI, db_enums.TIPO_INDICE_EVI):
            calcular_tendencia_area.delay(str(area.id), tipo)
            despachadas += 1
    return {"despachadas": despachadas}
