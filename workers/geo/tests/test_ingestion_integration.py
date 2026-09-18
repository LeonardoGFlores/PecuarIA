"""Testes de integracao do upsert contra Postgres real — ON CONFLICT e
especifico do dialeto, nao da para usar SQLite. Pulados automaticamente se
o banco configurado em DATABASE_URL nao estiver acessivel.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from app import db_enums
from app.db import get_engine, get_table
from app.ingestion.upsert import upsert_observacoes


@pytest.fixture
def conn():
    try:
        connection = get_engine().connect()
    except OperationalError:
        pytest.skip("Postgres local nao acessivel via DATABASE_URL")
    yield connection
    connection.close()


@pytest.fixture
def estacao_teste(conn):
    """Cria uma fazenda + estacao_meteorologica descartaveis e limpa no final."""
    fazenda_tbl = get_table("fazenda")
    estacao_tbl = get_table("estacao_meteorologica")

    fazenda_id = uuid.uuid4()
    conn.execute(
        fazenda_tbl.insert().values(
            id=fazenda_id,
            nome="Fazenda Teste Upsert",
            geom="SRID=4326;POLYGON((-47 -15, -47 -15.01, -46.99 -15.01, -46.99 -15, -47 -15))",
            fonte="teste_automatizado",
            status="DECLARADO",
            qualidade="MEDIA",
            versao=1,
        )
    )
    estacao_id = uuid.uuid4()
    conn.execute(
        estacao_tbl.insert().values(
            id=estacao_id,
            fonte=db_enums.FONTE_INMET,
            codigo_externo="TESTE001",
            nome="Estacao Teste",
            geom="SRID=4326;POINT(-47.0 -15.0)",
            tipo=db_enums.TIPO_ESTACAO_OBSERVADO,
            variaveis_disponiveis=[],
        )
    )
    conn.commit()

    yield estacao_id

    conn.execute(delete(estacao_tbl).where(estacao_tbl.c.id == estacao_id))
    conn.execute(delete(fazenda_tbl).where(fazenda_tbl.c.id == fazenda_id))
    conn.commit()


def test_upsert_insere_nova_observacao(conn, estacao_teste):
    linhas = [
        {
            "estacao_id": estacao_teste,
            "variavel": db_enums.VARIAVEL_TEMPERATURA,
            "timestamp": dt.datetime(2024, 1, 1, 12, tzinfo=dt.timezone.utc),
            "valor": 25.0,
            "unidade": "C",
            "status": db_enums.STATUS_OBSERVADO,
            "versao_processamento": "teste-v1",
        }
    ]
    afetadas = upsert_observacoes(conn, linhas)
    assert afetadas == 1

    tabela = get_table("observacao_meteorologica")
    linha = conn.execute(select(tabela).where(tabela.c.estacao_id == estacao_teste)).first()
    assert linha.valor == pytest.approx(25.0)


def test_upsert_mesmo_valor_nao_duplica_nem_conta_como_alteracao(conn, estacao_teste):
    linha = {
        "estacao_id": estacao_teste,
        "variavel": db_enums.VARIAVEL_TEMPERATURA,
        "timestamp": dt.datetime(2024, 1, 1, 12, tzinfo=dt.timezone.utc),
        "valor": 25.0,
        "unidade": "C",
        "status": db_enums.STATUS_OBSERVADO,
        "versao_processamento": "teste-v1",
    }
    upsert_observacoes(conn, [linha])
    afetadas = upsert_observacoes(conn, [dict(linha)])
    assert afetadas == 0  # WHERE valor IS DISTINCT FROM filtrou o no-op

    tabela = get_table("observacao_meteorologica")
    total = conn.execute(select(tabela).where(tabela.c.estacao_id == estacao_teste)).fetchall()
    assert len(total) == 1


def test_upsert_valor_diferente_atualiza_em_vez_de_duplicar(conn, estacao_teste):
    base = {
        "estacao_id": estacao_teste,
        "variavel": db_enums.VARIAVEL_TEMPERATURA,
        "timestamp": dt.datetime(2024, 1, 1, 12, tzinfo=dt.timezone.utc),
        "unidade": "C",
        "status": db_enums.STATUS_OBSERVADO,
        "versao_processamento": "teste-v1",
    }
    upsert_observacoes(conn, [{**base, "valor": 25.0}])
    afetadas = upsert_observacoes(conn, [{**base, "valor": 26.5}])
    assert afetadas == 1

    tabela = get_table("observacao_meteorologica")
    linhas = conn.execute(select(tabela).where(tabela.c.estacao_id == estacao_teste)).fetchall()
    assert len(linhas) == 1
    assert linhas[0].valor == pytest.approx(26.5)
