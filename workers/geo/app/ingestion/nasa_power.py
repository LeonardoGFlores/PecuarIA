"""Tasks Celery de ingestao do NASA POWER — fallback em grade, acionado sob
demanda quando a avaliacao de representatividade (`app.quality.
representatividade`) conclui que nenhuma estacao INMET candidata atinge nem
o patamar de auxiliar para alguma variavel de uma fazenda.

Uma estacao-grade por fazenda (nao compartilhavel — depende do centroide da
fazenda), criada preguiçosamente na primeira necessidade.
"""

from __future__ import annotations

import datetime as dt
import uuid

import httpx
from sqlalchemy import func, select, update

from app import db_enums
from app.clients import nasa_power as nasa_power_client
from app.config import get_settings
from app.db import get_engine, get_table
from app.ingestion.manifesto import IngestaoParcialError, rastrear_execucao
from app.ingestion.upsert import upsert_observacoes
from app.tasks import celery_app
from app.versioning import VERSAO_INGESTAO_NASA_POWER

OVERLAP_REFRESH_DIAS = 7

MAPA_PARAMETRO_VARIAVEL: dict[str, str] = {
    "PRECTOTCORR": db_enums.VARIAVEL_PRECIPITACAO,
    "T2M": db_enums.VARIAVEL_TEMPERATURA,
    "RH2M": db_enums.VARIAVEL_UMIDADE_RELATIVA,
    "ALLSKY_SFC_SW_DWN": db_enums.VARIAVEL_RADIACAO,
    "WS2M": db_enums.VARIAVEL_VENTO,
}


class FazendaNaoEncontradaError(RuntimeError):
    """A fazenda referenciada por uma task de ingestao nao existe mais —
    pode acontecer se ela foi excluida entre o enfileiramento e a execucao
    da task (ex.: uma mensagem que ficou parada na fila)."""


def garantir_estacao_grade(conn, fazenda_id: uuid.UUID) -> uuid.UUID:
    """Retorna o id da estacao-grade NASA POWER da fazenda, criando-a se
    ainda nao existir."""
    codigo_externo = f"FAZENDA:{fazenda_id}"
    tabela = get_table("estacao_meteorologica")
    existente = conn.execute(
        select(tabela.c.id).where(
            tabela.c.fonte == db_enums.FONTE_NASA_POWER, tabela.c.codigo_externo == codigo_externo
        )
    ).first()
    if existente is not None:
        return existente.id

    fazenda_tbl = get_table("fazenda")
    fazenda = conn.execute(
        select(
            fazenda_tbl.c.nome,
            func.ST_X(func.ST_Centroid(fazenda_tbl.c.geom)).label("lon"),
            func.ST_Y(func.ST_Centroid(fazenda_tbl.c.geom)).label("lat"),
        ).where(fazenda_tbl.c.id == fazenda_id)
    ).first()
    if fazenda is None:
        raise FazendaNaoEncontradaError(
            f"Fazenda {fazenda_id} nao encontrada — nao e possivel garantir a estacao-grade NASA POWER"
        )

    estacao_id = uuid.uuid4()
    conn.execute(
        tabela.insert().values(
            id=estacao_id,
            fonte=db_enums.FONTE_NASA_POWER,
            codigo_externo=codigo_externo,
            nome=f"NASA POWER - {fazenda.nome}",
            geom=f"SRID=4326;POINT({fazenda.lon} {fazenda.lat})",
            tipo=db_enums.TIPO_ESTACAO_GRADE,
            variaveis_disponiveis=[],
        )
    )
    conn.commit()
    return estacao_id


@celery_app.task(name="clima.nasa_power.ingerir_observacoes", queue="clima_nasa_power")
def ingerir_observacoes(fazenda_id: str) -> dict:
    settings = get_settings()
    engine = get_engine()
    fazenda_uuid = uuid.UUID(fazenda_id)
    hoje = dt.date.today()
    ontem = hoje - dt.timedelta(days=1)

    with engine.connect() as conn:
        estacao_id = garantir_estacao_grade(conn, fazenda_uuid)

        tabela_estacao = get_table("estacao_meteorologica")
        estacao_atual = conn.execute(
            select(tabela_estacao.c.periodo_fim_serie, tabela_estacao.c.variaveis_disponiveis).where(
                tabela_estacao.c.id == estacao_id
            )
        ).first()

        if estacao_atual.periodo_fim_serie is None:
            inicio = hoje - dt.timedelta(days=365 * settings.nasa_power_backfill_anos)
            modo = "backfill"
        else:
            inicio = estacao_atual.periodo_fim_serie.date() - dt.timedelta(days=OVERLAP_REFRESH_DIAS)
            modo = "refresh"

        if inicio > ontem:
            return {"status": "sem_janela_pendente"}

        fazenda_tbl = get_table("fazenda")
        ponto = conn.execute(
            select(
                func.ST_Y(func.ST_Centroid(fazenda_tbl.c.geom)).label("lat"),
                func.ST_X(func.ST_Centroid(fazenda_tbl.c.geom)).label("lon"),
            ).where(fazenda_tbl.c.id == fazenda_uuid)
        ).first()

        with rastrear_execucao(
            conn,
            tipo=db_enums.TIPO_EXECUCAO_INGESTAO_CLIMA,
            entrada_fontes=[f"NASA_POWER:fazenda={fazenda_id}"],
            parametros={
                "community": nasa_power_client.COMMUNITY,
                "parameters": nasa_power_client.PARAMETROS_PADRAO,
                "janela_inicio": inicio.isoformat(),
                "janela_fim": ontem.isoformat(),
                "modo": modo,
            },
            versao_pipeline=VERSAO_INGESTAO_NASA_POWER,
        ) as (_execucao_id, resultado):
            try:
                leituras, unidades = nasa_power_client.serie_diaria(ponto.lat, ponto.lon, inicio, ontem)
            except httpx.HTTPError as exc:
                raise IngestaoParcialError(
                    f"falha ao buscar NASA POWER para fazenda {fazenda_id}: {exc}"
                ) from exc

            linhas = []
            variaveis_vistas: set[str] = set()
            for leitura in leituras:
                timestamp = dt.datetime.combine(leitura.data, dt.time(12, 0), tzinfo=dt.timezone.utc)
                for parametro, valor in leitura.valores.items():
                    variavel = MAPA_PARAMETRO_VARIAVEL.get(parametro)
                    if variavel is None:
                        continue
                    linhas.append(
                        {
                            "estacao_id": estacao_id,
                            "variavel": variavel,
                            "timestamp": timestamp,
                            "valor": valor,
                            "unidade": unidades.get(parametro, "desconhecida"),
                            "status": db_enums.STATUS_ESTIMADO,
                            "versao_processamento": VERSAO_INGESTAO_NASA_POWER,
                        }
                    )
                    variaveis_vistas.add(variavel)

            afetadas = upsert_observacoes(conn, linhas)
            resultado["saida_referencias"].append(
                f"observacao_meteorologica:estacao={estacao_id}:linhas={afetadas}"
            )

            variaveis_atualizadas = sorted(set(estacao_atual.variaveis_disponiveis or []) | variaveis_vistas)
            conn.execute(
                update(tabela_estacao)
                .where(tabela_estacao.c.id == estacao_id)
                .values(
                    variaveis_disponiveis=variaveis_atualizadas,
                    periodo_fim_serie=dt.datetime.combine(ontem, dt.time(23, 59), tzinfo=dt.timezone.utc),
                )
            )
            conn.commit()

    return {"linhas_afetadas": afetadas}


@celery_app.task(name="clima.nasa_power.despachar_refresh")
def despachar_refresh() -> dict:
    """Refresh semanal das estacoes-grade ja criadas (a criacao inicial e
    sempre sob demanda, via `quality.representatividade`)."""
    engine = get_engine()
    with engine.connect() as conn:
        tabela = get_table("estacao_meteorologica")
        estacoes = conn.execute(
            select(tabela.c.codigo_externo).where(tabela.c.fonte == db_enums.FONTE_NASA_POWER)
        ).fetchall()

    despachadas = 0
    for estacao in estacoes:
        _, fazenda_id = estacao.codigo_externo.split(":", 1)
        ingerir_observacoes.delay(fazenda_id)
        despachadas += 1
    return {"despachadas": despachadas}
