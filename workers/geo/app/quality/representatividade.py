"""Avaliacao de representatividade de estacoes meteorologicas por fazenda.

Fluxo (docs/specs da Fase 2): busca candidatas num raio da fazenda, avalia
completude/atualizacao/consistencia de cada uma por variavel numa janela de
365 dias, decide papel (referencia/auxiliar) e grava em
`avaliacao_representatividade`. Nunca escolhe a mais proxima sem antes
filtrar pelos 3 criterios de qualidade.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app import db_enums
from app.config import get_settings
from app.db import get_engine, get_table
from app.ingestion import nasa_power as nasa_power_ingestion
from app.ingestion.manifesto import rastrear_execucao
from app.quality import metrics
from app.tasks import celery_app
from app.versioning import VERSAO_QUALIDADE_REPRESENTATIVIDADE


def _buscar_candidatas(conn, fazenda_id: uuid.UUID, raio_km: float) -> list[dict]:
    """Estacoes dentro de `raio_km` do centroide da fazenda, com distancia em km.

    Consulta espacial em SQL puro (nao via GeoAlchemy2 Core): o worker trata
    colunas de geometria como opacas (ver docstring de `app.db`), so o
    Postgres/PostGIS manipula o conteudo delas.
    """
    query = text(
        """
        SELECT
            e.id AS estacao_id,
            e.tipo AS tipo,
            ST_Distance(e.geom::geography, ST_Centroid(f.geom)::geography) / 1000.0 AS distancia_km
        FROM estacao_meteorologica e, fazenda f
        WHERE f.id = :fazenda_id
          AND ST_DWithin(e.geom::geography, ST_Centroid(f.geom)::geography, :raio_metros)
        """
    )
    linhas = conn.execute(query, {"fazenda_id": str(fazenda_id), "raio_metros": raio_km * 1000}).mappings().all()
    return [dict(linha) for linha in linhas]


def _avaliar_candidata(
    conn, estacao_id, tipo_estacao: str, distancia_km: float, variavel: str, janela_inicio: dt.datetime, janela_fim: dt.datetime
) -> dict | None:
    obs_tbl = get_table("observacao_meteorologica")
    linhas = conn.execute(
        select(obs_tbl.c.id, obs_tbl.c.timestamp, obs_tbl.c.valor).where(
            obs_tbl.c.estacao_id == estacao_id,
            obs_tbl.c.variavel == variavel,
            obs_tbl.c.timestamp >= janela_inicio,
            obs_tbl.c.timestamp <= janela_fim,
        )
    ).fetchall()
    if not linhas:
        return None  # candidata sem observacao na janela nao gera linha (nao forcar null)

    dias_esperados = max((janela_fim - janela_inicio).days, 1)
    dias_com_dado = len({linha.timestamp.date() for linha in linhas})
    idade_dias = (janela_fim - max(linha.timestamp for linha in linhas)).total_seconds() / 86400

    valores = [linha.valor for linha in linhas]
    suspeitos = metrics.marcar_suspeitos(valores, variavel)
    pct_suspeitas = sum(suspeitos) / len(valores)

    ids_suspeitos = [linha.id for linha, suspeito in zip(linhas, suspeitos) if suspeito]
    if ids_suspeitos:
        conn.execute(update(obs_tbl).where(obs_tbl.c.id.in_(ids_suspeitos)).values(flag_qualidade="suspeito"))

    return {
        "estacao_id": estacao_id,
        "tipo_estacao": tipo_estacao,
        "distancia_km": distancia_km,
        "criterio_completude": metrics.nivel_completude(dias_com_dado, dias_esperados),
        "criterio_atualizacao": metrics.nivel_atualizacao(idade_dias),
        "criterio_consistencia": metrics.nivel_consistencia(pct_suspeitas),
    }


def _decidir_papeis(avaliacoes: list[dict]) -> dict:
    """Regras (docs/specs da Fase 2):
    1. Candidata `tipo=grade` e sempre AUXILIAR — nunca REFERENCIA, regra dura
       independente de qualidade (e o fallback deliberado quando nao ha INMET bom).
    2. Candidata `observado` so e elegivel a REFERENCIA se NENHUM dos 3
       criterios for INSUFICIENTE (gate por piso, nao media).
    3. Entre as elegiveis, a de menor distancia_km vence a REFERENCIA —
       proximidade e o desempate final, nunca o primeiro filtro.
    4. As demais `observado` (nao escolhidas) viram AUXILIAR se completude e
       atualizacao forem ao menos REGULAR; senao ficam sem papel (None) e
       nao geram linha — mesma logica de "nao forcar" de candidatas sem dado.
    """
    elegiveis_referencia = [
        a
        for a in avaliacoes
        if a["tipo_estacao"] == db_enums.TIPO_ESTACAO_OBSERVADO
        and db_enums.NIVEL_INSUFICIENTE
        not in (a["criterio_completude"], a["criterio_atualizacao"], a["criterio_consistencia"])
    ]
    referencia_id = None
    if elegiveis_referencia:
        referencia_id = min(elegiveis_referencia, key=lambda a: a["distancia_km"])["estacao_id"]

    papeis: dict = {}
    for avaliacao in avaliacoes:
        if avaliacao["estacao_id"] == referencia_id:
            papeis[avaliacao["estacao_id"]] = db_enums.PAPEL_REFERENCIA
        elif avaliacao["tipo_estacao"] == db_enums.TIPO_ESTACAO_GRADE:
            papeis[avaliacao["estacao_id"]] = db_enums.PAPEL_AUXILIAR
        elif (
            avaliacao["criterio_completude"] != db_enums.NIVEL_INSUFICIENTE
            and avaliacao["criterio_atualizacao"] != db_enums.NIVEL_INSUFICIENTE
        ):
            papeis[avaliacao["estacao_id"]] = db_enums.PAPEL_AUXILIAR
        else:
            papeis[avaliacao["estacao_id"]] = None
    return papeis


def _upsert_avaliacao(conn, fazenda_id: uuid.UUID, variavel: str, avaliacao: dict, papel: str) -> None:
    tabela = get_table("avaliacao_representatividade")
    stmt = pg_insert(tabela).values(
        id=uuid.uuid4(),
        fazenda_id=fazenda_id,
        estacao_id=avaliacao["estacao_id"],
        variavel=variavel,
        distancia_km=avaliacao["distancia_km"],
        criterio_completude=avaliacao["criterio_completude"],
        criterio_atualizacao=avaliacao["criterio_atualizacao"],
        criterio_consistencia=avaliacao["criterio_consistencia"],
        papel=papel,
        versao_algoritmo=VERSAO_QUALIDADE_REPRESENTATIVIDADE,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_avaliacao_fazenda_estacao_variavel",
        set_={
            "distancia_km": stmt.excluded.distancia_km,
            "criterio_completude": stmt.excluded.criterio_completude,
            "criterio_atualizacao": stmt.excluded.criterio_atualizacao,
            "criterio_consistencia": stmt.excluded.criterio_consistencia,
            "papel": stmt.excluded.papel,
            "versao_algoritmo": stmt.excluded.versao_algoritmo,
            "calculado_em": func.now(),
        },
    )
    conn.execute(stmt)


@celery_app.task(name="qualidade.avaliar_fazenda", queue="qualidade")
def avaliar_fazenda(fazenda_id: str) -> dict:
    settings = get_settings()
    engine = get_engine()
    fazenda_uuid = uuid.UUID(fazenda_id)
    agora = dt.datetime.now(dt.timezone.utc)
    janela_inicio = agora - dt.timedelta(days=settings.janela_representatividade_dias)

    with engine.connect() as conn:
        candidatas = _buscar_candidatas(conn, fazenda_uuid, settings.raio_representatividade_km)

        with rastrear_execucao(
            conn,
            tipo=db_enums.TIPO_EXECUCAO_AVALIACAO_REPRESENTATIVIDADE,
            entrada_fontes=[f"estacao:{c['estacao_id']}" for c in candidatas],
            parametros={
                "fazenda_id": fazenda_id,
                "raio_km": settings.raio_representatividade_km,
                "janela_dias": settings.janela_representatividade_dias,
            },
            versao_pipeline=VERSAO_QUALIDADE_REPRESENTATIVIDADE,
        ) as (_execucao_id, resultado):
            avaliacoes_por_variavel: dict[str, list[dict]] = {}
            for candidata in candidatas:
                for variavel in db_enums.TODAS_VARIAVEIS:
                    avaliacao = _avaliar_candidata(
                        conn,
                        candidata["estacao_id"],
                        candidata["tipo"],
                        candidata["distancia_km"],
                        variavel,
                        janela_inicio,
                        agora,
                    )
                    if avaliacao is not None:
                        avaliacoes_por_variavel.setdefault(variavel, []).append(avaliacao)

            total_gravadas = 0
            variaveis_cobertas: set[str] = set()
            for variavel, avaliacoes in avaliacoes_por_variavel.items():
                papeis = _decidir_papeis(avaliacoes)
                for avaliacao in avaliacoes:
                    papel = papeis[avaliacao["estacao_id"]]
                    if papel is None:
                        continue
                    variaveis_cobertas.add(variavel)
                    _upsert_avaliacao(conn, fazenda_uuid, variavel, avaliacao, papel)
                    total_gravadas += 1
                    resultado["saida_referencias"].append(
                        f"avaliacao_representatividade:fazenda={fazenda_id}:variavel={variavel}:"
                        f"estacao={avaliacao['estacao_id']}:papel={papel}"
                    )

            # Fallback NASA POWER: acionado uma vez por fazenda (nao por
            # variavel — a API retorna todos os parametros numa unica
            # chamada) quando pelo menos uma variavel ficou sem nenhuma
            # candidata com papel atribuido (nem referencia, nem auxiliar).
            variaveis_sem_cobertura = [v for v in db_enums.TODAS_VARIAVEIS if v not in variaveis_cobertas]
            if variaveis_sem_cobertura:
                nasa_power_ingestion.ingerir_observacoes.delay(fazenda_id)
                resultado["saida_referencias"].append(
                    "NASA_POWER:fallback_acionado:variaveis_sem_cobertura="
                    + ",".join(variaveis_sem_cobertura)
                )
            conn.commit()

    return {
        "candidatas": len(candidatas),
        "avaliacoes_gravadas": total_gravadas,
        "fallback_nasa_power_acionado": bool(variaveis_sem_cobertura),
    }


@celery_app.task(name="qualidade.despachar_avaliacoes", queue="qualidade")
def despachar_avaliacoes() -> dict:
    engine = get_engine()
    with engine.connect() as conn:
        fazenda_tbl = get_table("fazenda")
        fazendas = conn.execute(select(fazenda_tbl.c.id)).fetchall()

    for fazenda in fazendas:
        avaliar_fazenda.delay(str(fazenda.id))
    return {"despachadas": len(fazendas)}
