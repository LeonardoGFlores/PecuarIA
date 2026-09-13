"""Testes de integracao das tasks de ingestao INMET contra Postgres real.
Chamadas HTTP mockadas (sem rede real). Pulados se DATABASE_URL nao
estiver acessivel."""

from __future__ import annotations

import datetime as dt
import uuid
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from app import db_enums
from app.clients.inmet import EstacaoInmet, LeituraInmet
from app.db import get_engine, get_table
from app.ingestion import inmet as inmet_ingestion


@pytest.fixture
def conn():
    try:
        connection = get_engine().connect()
    except OperationalError:
        pytest.skip("Postgres local nao acessivel via DATABASE_URL")
    yield connection
    connection.close()


def test_sincronizar_catalogo_insere_estacao_nova(conn):
    codigo = f"TESTE{uuid.uuid4().hex[:6].upper()}"
    fake_estacao = EstacaoInmet(codigo=codigo, nome="Estacao Fake", latitude=-15.5, longitude=-47.5, altitude=1000.0)

    with patch("app.ingestion.inmet.inmet_client.listar_estacoes", return_value=[fake_estacao]):
        resultado = inmet_ingestion.sincronizar_catalogo()

    assert resultado["novas"] == 1

    tabela = get_table("estacao_meteorologica")
    linha = conn.execute(
        select(tabela).where(tabela.c.fonte == db_enums.FONTE_INMET, tabela.c.codigo_externo == codigo)
    ).first()
    assert linha is not None
    assert linha.nome == "Estacao Fake"
    assert linha.altitude_m == pytest.approx(1000.0)

    conn.execute(delete(tabela).where(tabela.c.id == linha.id))
    conn.commit()


def test_sincronizar_catalogo_atualiza_estacao_existente_sem_duplicar(conn):
    codigo = f"TESTE{uuid.uuid4().hex[:6].upper()}"
    tabela = get_table("estacao_meteorologica")
    estacao_id = uuid.uuid4()
    conn.execute(
        tabela.insert().values(
            id=estacao_id,
            fonte=db_enums.FONTE_INMET,
            codigo_externo=codigo,
            nome="Nome Antigo",
            geom="SRID=4326;POINT(-47.5 -15.5)",
            tipo=db_enums.TIPO_ESTACAO_OBSERVADO,
            variaveis_disponiveis=[],
        )
    )
    conn.commit()

    fake_estacao = EstacaoInmet(codigo=codigo, nome="Nome Novo", latitude=-15.6, longitude=-47.6, altitude=1200.0)
    with patch("app.ingestion.inmet.inmet_client.listar_estacoes", return_value=[fake_estacao]):
        resultado = inmet_ingestion.sincronizar_catalogo()

    assert resultado["atualizadas"] >= 1

    linhas = conn.execute(select(tabela).where(tabela.c.codigo_externo == codigo)).fetchall()
    assert len(linhas) == 1  # nao duplicou
    assert linhas[0].nome == "Nome Novo"

    conn.execute(delete(tabela).where(tabela.c.id == estacao_id))
    conn.commit()


def _criar_estacao(conn, periodo_fim_serie=None):
    tabela = get_table("estacao_meteorologica")
    estacao_id = uuid.uuid4()
    codigo = f"TESTE{uuid.uuid4().hex[:6].upper()}"
    conn.execute(
        tabela.insert().values(
            id=estacao_id,
            fonte=db_enums.FONTE_INMET,
            codigo_externo=codigo,
            nome="Estacao Teste",
            geom="SRID=4326;POINT(-47.5 -15.5)",
            tipo=db_enums.TIPO_ESTACAO_OBSERVADO,
            variaveis_disponiveis=[],
            periodo_fim_serie=periodo_fim_serie,
        )
    )
    conn.commit()
    return estacao_id, codigo


def test_despachar_incrementais_backfill_para_estacao_sem_historico(conn):
    estacao_id, codigo = _criar_estacao(conn, periodo_fim_serie=None)
    try:
        with patch("app.ingestion.inmet.ingerir_observacoes.delay") as mock_delay:
            inmet_ingestion.despachar_incrementais()
        chamadas = [c for c in mock_delay.call_args_list if c.args[0] == str(estacao_id)]
        assert len(chamadas) == 1
        assert chamadas[0].args[4] == "backfill"
    finally:
        est_tbl = get_table("estacao_meteorologica")
        conn.execute(delete(est_tbl).where(est_tbl.c.id == estacao_id))
        conn.commit()


def test_despachar_incrementais_incremental_para_estacao_com_historico(conn):
    fim_antigo = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=10)
    estacao_id, codigo = _criar_estacao(conn, periodo_fim_serie=fim_antigo)
    try:
        with patch("app.ingestion.inmet.ingerir_observacoes.delay") as mock_delay:
            inmet_ingestion.despachar_incrementais()
        chamadas = [c for c in mock_delay.call_args_list if c.args[0] == str(estacao_id)]
        assert len(chamadas) == 1
        assert chamadas[0].args[4] == "incremental"
        inicio_esperado = (fim_antigo.date() - dt.timedelta(days=inmet_ingestion.OVERLAP_INCREMENTAL_DIAS)).isoformat()
        assert chamadas[0].args[2] == inicio_esperado
    finally:
        est_tbl = get_table("estacao_meteorologica")
        conn.execute(delete(est_tbl).where(est_tbl.c.id == estacao_id))
        conn.commit()


def test_despachar_incrementais_pula_estacao_com_marca_dagua_futura(conn):
    # Guarda defensiva: so ha algo a buscar se `inicio <= ontem`. Isso so deixa
    # de valer numa marca d'agua no futuro (nunca deveria acontecer em uso
    # normal, ja que a propria ingestao nunca avanca alem de "ontem" — mas o
    # despacho precisa ser seguro mesmo se o dado ficar inconsistente).
    fim_futuro = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=10)
    estacao_id, codigo = _criar_estacao(conn, periodo_fim_serie=fim_futuro)
    try:
        with patch("app.ingestion.inmet.ingerir_observacoes.delay") as mock_delay:
            inmet_ingestion.despachar_incrementais()
        chamadas = [c for c in mock_delay.call_args_list if c.args[0] == str(estacao_id)]
        assert len(chamadas) == 0
    finally:
        est_tbl = get_table("estacao_meteorologica")
        conn.execute(delete(est_tbl).where(est_tbl.c.id == estacao_id))
        conn.commit()


def test_ingerir_observacoes_grava_linhas_e_avanca_marca_dagua(conn):
    estacao_id, codigo = _criar_estacao(conn, periodo_fim_serie=None)
    leituras_fake = [
        LeituraInmet(
            timestamp=dt.datetime(2024, 1, 1, 12, tzinfo=dt.timezone.utc),
            valores={db_enums.VARIAVEL_TEMPERATURA: 25.0, db_enums.VARIAVEL_PRECIPITACAO: 0.0},
        )
    ]
    try:
        with patch("app.ingestion.inmet.inmet_client.serie_horaria", return_value=leituras_fake):
            resultado = inmet_ingestion.ingerir_observacoes(
                str(estacao_id), codigo, "2024-01-01", "2024-01-31", "backfill"
            )
        assert resultado["linhas_afetadas"] == 2

        obs_tbl = get_table("observacao_meteorologica")
        linhas = conn.execute(select(obs_tbl).where(obs_tbl.c.estacao_id == estacao_id)).fetchall()
        assert len(linhas) == 2

        est_tbl = get_table("estacao_meteorologica")
        estacao_atualizada = conn.execute(select(est_tbl).where(est_tbl.c.id == estacao_id)).first()
        assert estacao_atualizada.periodo_fim_serie.date() == dt.date(2024, 1, 31)
        assert set(estacao_atualizada.variaveis_disponiveis) == {
            db_enums.VARIAVEL_TEMPERATURA,
            db_enums.VARIAVEL_PRECIPITACAO,
        }
    finally:
        obs_tbl = get_table("observacao_meteorologica")
        est_tbl = get_table("estacao_meteorologica")
        exec_tbl = get_table("execucao_processamento")
        conn.execute(delete(obs_tbl).where(obs_tbl.c.estacao_id == estacao_id))
        conn.execute(delete(exec_tbl).where(exec_tbl.c.parametros["estacao_id"].astext == str(estacao_id)))
        conn.execute(delete(est_tbl).where(est_tbl.c.id == estacao_id))
        conn.commit()


def test_ingerir_observacoes_falha_no_meio_preserva_progresso_como_parcial(conn):
    estacao_id, codigo = _criar_estacao(conn, periodo_fim_serie=None)

    leitura_janeiro = [
        LeituraInmet(
            timestamp=dt.datetime(2024, 1, 1, 12, tzinfo=dt.timezone.utc),
            valores={db_enums.VARIAVEL_TEMPERATURA: 25.0},
        )
    ]

    def serie_horaria_fake(codigo_estacao, inicio, fim):
        if inicio.month == 1:
            return leitura_janeiro
        raise httpx.ConnectError("falha simulada de rede")

    with patch("app.ingestion.inmet.inmet_client.serie_horaria", side_effect=serie_horaria_fake):
        # janela cobrindo janeiro (sucesso) e fevereiro (falha). IngestaoParcialError
        # nao propaga (ver manifesto.rastrear_execucao) — a task termina normalmente,
        # com o progresso de janeiro preservado e o manifesto marcado como PARCIAL.
        resultado = inmet_ingestion.ingerir_observacoes(str(estacao_id), codigo, "2024-01-01", "2024-02-28", "backfill")
    assert resultado["linhas_afetadas"] == 1
    assert resultado["janelas_concluidas"] == 1
    assert resultado["janelas_totais"] == 2

    obs_tbl = get_table("observacao_meteorologica")
    linhas = conn.execute(select(obs_tbl).where(obs_tbl.c.estacao_id == estacao_id)).fetchall()
    assert len(linhas) == 1  # janeiro foi gravado antes da falha em fevereiro

    exec_tbl = get_table("execucao_processamento")
    execucao = conn.execute(
        select(exec_tbl)
        .where(exec_tbl.c.parametros["estacao_id"].astext == str(estacao_id))
        .order_by(exec_tbl.c.iniciado_em.desc())
    ).first()
    assert execucao.status == db_enums.STATUS_EXECUCAO_PARCIAL
    assert len(execucao.saida_referencias) == 1

    conn.execute(delete(obs_tbl).where(obs_tbl.c.estacao_id == estacao_id))
    conn.execute(delete(exec_tbl).where(exec_tbl.c.parametros["estacao_id"].astext == str(estacao_id)))
    est_tbl = get_table("estacao_meteorologica")
    conn.execute(delete(est_tbl).where(est_tbl.c.id == estacao_id))
    conn.commit()
