"""Testes de integracao do manifesto de execucao contra Postgres real.
Pulados automaticamente se DATABASE_URL nao estiver acessivel."""

from __future__ import annotations

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from app import db_enums
from app.db import get_engine, get_table
from app.ingestion.manifesto import IngestaoParcialError, rastrear_execucao


@pytest.fixture
def conn():
    try:
        connection = get_engine().connect()
    except OperationalError:
        pytest.skip("Postgres local nao acessivel via DATABASE_URL")
    yield connection
    connection.close()


def _limpar(conn, execucao_id):
    tabela = get_table("execucao_processamento")
    conn.execute(delete(tabela).where(tabela.c.id == execucao_id))
    conn.commit()


def test_rastrear_execucao_sucesso_grava_status_e_saida(conn):
    with rastrear_execucao(
        conn,
        tipo=db_enums.TIPO_EXECUCAO_INGESTAO_CLIMA,
        entrada_fontes=["INMET:TESTE001"],
        parametros={"modo": "teste"},
        versao_pipeline="teste-v1",
    ) as (execucao_id, resultado):
        resultado["saida_referencias"].append("observacao_meteorologica:linhas=3")

    tabela = get_table("execucao_processamento")
    linha = conn.execute(select(tabela).where(tabela.c.id == execucao_id)).first()
    assert linha.status == db_enums.STATUS_EXECUCAO_SUCESSO
    assert linha.concluido_em is not None
    assert linha.saida_referencias == ["observacao_meteorologica:linhas=3"]

    _limpar(conn, execucao_id)


def test_rastrear_execucao_falha_grava_status_e_repropaga(conn):
    execucao_id_capturado = {}
    with pytest.raises(ValueError):
        with rastrear_execucao(
            conn,
            tipo=db_enums.TIPO_EXECUCAO_INGESTAO_CLIMA,
            entrada_fontes=["INMET:TESTE001"],
            parametros={},
            versao_pipeline="teste-v1",
        ) as (execucao_id, _resultado):
            execucao_id_capturado["id"] = execucao_id
            raise ValueError("falha simulada")

    tabela = get_table("execucao_processamento")
    linha = conn.execute(select(tabela).where(tabela.c.id == execucao_id_capturado["id"])).first()
    assert linha.status == db_enums.STATUS_EXECUCAO_FALHA
    assert linha.parametros["erro"] == "falha simulada"

    _limpar(conn, execucao_id_capturado["id"])


def test_rastrear_execucao_parcial_nao_repropaga(conn):
    with rastrear_execucao(
        conn,
        tipo=db_enums.TIPO_EXECUCAO_INGESTAO_CLIMA,
        entrada_fontes=["INMET:TESTE001"],
        parametros={},
        versao_pipeline="teste-v1",
    ) as (execucao_id, resultado):
        resultado["saida_referencias"].append("observacao_meteorologica:linhas=1")
        raise IngestaoParcialError("timeout na metade do backfill")

    tabela = get_table("execucao_processamento")
    linha = conn.execute(select(tabela).where(tabela.c.id == execucao_id)).first()
    assert linha.status == db_enums.STATUS_EXECUCAO_PARCIAL
    assert linha.saida_referencias == ["observacao_meteorologica:linhas=1"]
    assert "timeout" in linha.parametros["erro"]

    _limpar(conn, execucao_id)
