"""Tasks Celery de ingestao do INMET: sincronizacao de catalogo e
observacoes (backfill/incremental).

Ver docstring de `app.clients.inmet` para as ressalvas sobre nomes de campo
nao confirmados contra a API real.
"""

from __future__ import annotations

import datetime as dt
import logging
import uuid

import httpx
from sqlalchemy import select, update

from app import db_enums
from app.clients import inmet as inmet_client
from app.config import get_settings
from app.db import get_engine, get_table
from app.ingestion.manifesto import IngestaoParcialError, rastrear_execucao
from app.ingestion.upsert import upsert_observacoes
from app.tasks import celery_app
from app.versioning import VERSAO_INGESTAO_INMET

logger = logging.getLogger(__name__)

OVERLAP_INCREMENTAL_DIAS = 2


def _dividir_em_meses(inicio: dt.date, fim: dt.date) -> list[tuple[dt.date, dt.date]]:
    """Divide [inicio, fim] em janelas mensais.

    Evita pedir anos de dados horarios numa unica chamada (resposta gigante,
    risco de timeout) e permite que uma falha no meio de um backfill longo
    preserve o progresso ja feito, gravado como PARCIAL em vez de FALHA
    total (ver `IngestaoParcialError`).
    """
    janelas: list[tuple[dt.date, dt.date]] = []
    cursor = inicio
    while cursor <= fim:
        proximo_mes = (cursor.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
        fim_janela = min(fim, proximo_mes - dt.timedelta(days=1))
        janelas.append((cursor, fim_janela))
        cursor = fim_janela + dt.timedelta(days=1)
    return janelas


@celery_app.task(name="clima.inmet.sincronizar_catalogo")
def sincronizar_catalogo() -> dict:
    """Upsert do catalogo de estacoes automaticas a partir de `/estacoes/T`."""
    engine = get_engine()
    with engine.connect() as conn:
        with rastrear_execucao(
            conn,
            tipo=db_enums.TIPO_EXECUCAO_INGESTAO_CLIMA,
            entrada_fontes=["INMET:catalogo_estacoes"],
            parametros={"endpoint": "/estacoes/T"},
            versao_pipeline=VERSAO_INGESTAO_INMET,
        ) as (_execucao_id, resultado):
            estacoes_remotas = inmet_client.listar_estacoes()
            tabela = get_table("estacao_meteorologica")

            novas = 0
            atualizadas = 0
            for estacao in estacoes_remotas:
                existente = conn.execute(
                    select(tabela.c.id).where(
                        tabela.c.fonte == db_enums.FONTE_INMET,
                        tabela.c.codigo_externo == estacao.codigo,
                    )
                ).first()
                geom = f"SRID=4326;POINT({estacao.longitude} {estacao.latitude})"
                if existente is None:
                    conn.execute(
                        tabela.insert().values(
                            id=uuid.uuid4(),
                            fonte=db_enums.FONTE_INMET,
                            codigo_externo=estacao.codigo,
                            nome=estacao.nome,
                            geom=geom,
                            altitude_m=estacao.altitude,
                            tipo=db_enums.TIPO_ESTACAO_OBSERVADO,
                            variaveis_disponiveis=[],
                        )
                    )
                    novas += 1
                else:
                    conn.execute(
                        update(tabela)
                        .where(tabela.c.id == existente.id)
                        .values(nome=estacao.nome, geom=geom, altitude_m=estacao.altitude)
                    )
                    atualizadas += 1
            conn.commit()
            resultado["saida_referencias"].append(
                f"estacao_meteorologica:fonte=INMET:novas={novas}:atualizadas={atualizadas}"
            )
    return {"novas": novas, "atualizadas": atualizadas}


@celery_app.task(name="clima.inmet.despachar_incrementais")
def despachar_incrementais() -> dict:
    """Decide, por estacao INMET cadastrada, se e backfill ou incremental, e
    despacha `ingerir_observacoes` para cada uma que tiver janela pendente."""
    settings = get_settings()
    engine = get_engine()
    hoje = dt.date.today()
    ontem = hoje - dt.timedelta(days=1)

    with engine.connect() as conn:
        tabela = get_table("estacao_meteorologica")
        estacoes = conn.execute(
            select(tabela.c.id, tabela.c.codigo_externo, tabela.c.periodo_fim_serie).where(
                tabela.c.fonte == db_enums.FONTE_INMET
            )
        ).fetchall()

    despachadas = 0
    for estacao in estacoes:
        if estacao.periodo_fim_serie is None:
            inicio = hoje - dt.timedelta(days=365 * settings.inmet_backfill_anos)
            modo = "backfill"
        else:
            inicio = estacao.periodo_fim_serie.date() - dt.timedelta(days=OVERLAP_INCREMENTAL_DIAS)
            modo = "incremental"
        if inicio > ontem:
            continue  # nada novo a buscar ainda

        ingerir_observacoes.delay(str(estacao.id), estacao.codigo_externo, inicio.isoformat(), ontem.isoformat(), modo)
        despachadas += 1
    return {"despachadas": despachadas}


@celery_app.task(name="clima.inmet.ingerir_observacoes", queue="clima_inmet")
def ingerir_observacoes(estacao_id: str, codigo_externo: str, inicio_iso: str, fim_iso: str, modo: str) -> dict:
    """Busca e grava observacoes de uma estacao numa janela [inicio, fim],
    dividida em blocos mensais (ver `_dividir_em_meses`)."""
    inicio = dt.date.fromisoformat(inicio_iso)
    fim = dt.date.fromisoformat(fim_iso)
    engine = get_engine()

    with engine.connect() as conn:
        with rastrear_execucao(
            conn,
            tipo=db_enums.TIPO_EXECUCAO_INGESTAO_CLIMA,
            entrada_fontes=[f"INMET:{codigo_externo}"],
            parametros={"estacao_id": estacao_id, "janela_inicio": inicio_iso, "janela_fim": fim_iso, "modo": modo},
            versao_pipeline=VERSAO_INGESTAO_INMET,
        ) as (_execucao_id, resultado):
            tabela_estacao = get_table("estacao_meteorologica")
            estacao_uuid = uuid.UUID(estacao_id)
            total_afetadas = 0
            janelas_concluidas = 0
            variaveis_vistas: set[str] = set()
            janelas = _dividir_em_meses(inicio, fim)

            for indice, (janela_inicio, janela_fim) in enumerate(janelas):
                try:
                    leituras = inmet_client.serie_horaria(codigo_externo, janela_inicio, janela_fim)
                except httpx.HTTPError as exc:
                    raise IngestaoParcialError(
                        f"falha ao buscar janela {janela_inicio}..{janela_fim} da estacao "
                        f"{codigo_externo} ({indice}/{len(janelas)} janelas concluidas antes da falha): {exc}"
                    ) from exc

                linhas = [
                    {
                        "estacao_id": estacao_uuid,
                        "variavel": variavel,
                        "timestamp": leitura.timestamp,
                        "valor": valor,
                        "unidade": inmet_client.UNIDADE_POR_VARIAVEL[variavel],
                        "status": db_enums.STATUS_OBSERVADO,
                        "versao_processamento": VERSAO_INGESTAO_INMET,
                    }
                    for leitura in leituras
                    for variavel, valor in leitura.valores.items()
                ]
                afetadas = upsert_observacoes(conn, linhas)
                total_afetadas += afetadas
                variaveis_vistas.update(v for leitura in leituras for v in leitura.valores)
                resultado["saida_referencias"].append(
                    f"observacao_meteorologica:estacao={estacao_id}:janela={janela_inicio}..{janela_fim}:linhas={afetadas}"
                )

                # avanca a marca d'agua a cada janela concluida — se uma janela
                # posterior falhar, a proxima execucao nao reprocessa o que ja deu certo.
                _atualizar_estacao_pos_janela(conn, tabela_estacao, estacao_uuid, janela_fim, variaveis_vistas, leituras)
                janelas_concluidas += 1

    return {"linhas_afetadas": total_afetadas, "janelas_concluidas": janelas_concluidas, "janelas_totais": len(janelas)}


def _atualizar_estacao_pos_janela(conn, tabela_estacao, estacao_uuid, janela_fim, variaveis_vistas, leituras) -> None:
    estacao_atual = conn.execute(
        select(tabela_estacao.c.variaveis_disponiveis, tabela_estacao.c.periodo_inicio_serie).where(
            tabela_estacao.c.id == estacao_uuid
        )
    ).first()
    variaveis_atualizadas = sorted(set(estacao_atual.variaveis_disponiveis or []) | variaveis_vistas)
    valores_update = {
        "variaveis_disponiveis": variaveis_atualizadas,
        "periodo_fim_serie": dt.datetime.combine(janela_fim, dt.time(23, 59), tzinfo=dt.timezone.utc),
    }
    if estacao_atual.periodo_inicio_serie is None and leituras:
        valores_update["periodo_inicio_serie"] = min(leitura.timestamp for leitura in leituras)
    conn.execute(update(tabela_estacao).where(tabela_estacao.c.id == estacao_uuid).values(**valores_update))
    conn.commit()
