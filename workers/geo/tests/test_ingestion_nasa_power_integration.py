"""Testes de integracao da ingestao NASA POWER contra Postgres real.
Chamadas HTTP mockadas (sem rede real). Pulados se DATABASE_URL nao
estiver acessivel."""

from __future__ import annotations

import datetime as dt
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from app import db_enums
from app.clients.nasa_power import LeituraNasaPower
from app.db import get_engine, get_table
from app.ingestion import nasa_power as nasa_power_ingestion


@pytest.fixture
def conn():
    try:
        connection = get_engine().connect()
    except OperationalError:
        pytest.skip("Postgres local nao acessivel via DATABASE_URL")
    yield connection
    connection.close()


@pytest.fixture
def fazenda_id(conn):
    tabela = get_table("fazenda")
    fid = uuid.uuid4()
    conn.execute(
        tabela.insert().values(
            id=fid,
            nome="Fazenda Teste NASA POWER",
            geom="SRID=4326;POLYGON((-47 -15, -47 -15.01, -46.99 -15.01, -46.99 -15, -47 -15))",
            fonte="teste_automatizado",
            status="DECLARADO",
            qualidade="MEDIA",
            versao=1,
        )
    )
    conn.commit()
    yield fid

    obs_tbl = get_table("observacao_meteorologica")
    est_tbl = get_table("estacao_meteorologica")
    exec_tbl = get_table("execucao_processamento")
    estacoes = conn.execute(
        select(est_tbl.c.id).where(est_tbl.c.codigo_externo == f"FAZENDA:{fid}")
    ).fetchall()
    for estacao in estacoes:
        conn.execute(delete(obs_tbl).where(obs_tbl.c.estacao_id == estacao.id))
    conn.execute(delete(est_tbl).where(est_tbl.c.codigo_externo == f"FAZENDA:{fid}"))
    conn.execute(delete(exec_tbl).where(exec_tbl.c.entrada_fontes.contains([f"NASA_POWER:fazenda={fid}"])))
    conn.execute(delete(tabela := get_table("fazenda")).where(tabela.c.id == fid))
    conn.commit()


def test_garantir_estacao_grade_cria_uma_vez_por_fazenda(conn, fazenda_id):
    id1 = nasa_power_ingestion.garantir_estacao_grade(conn, fazenda_id)
    id2 = nasa_power_ingestion.garantir_estacao_grade(conn, fazenda_id)
    assert id1 == id2

    tabela = get_table("estacao_meteorologica")
    linha = conn.execute(select(tabela).where(tabela.c.id == id1)).first()
    assert linha.fonte == db_enums.FONTE_NASA_POWER
    assert linha.tipo == db_enums.TIPO_ESTACAO_GRADE
    assert linha.codigo_externo == f"FAZENDA:{fazenda_id}"


def test_ingerir_observacoes_grava_linhas_como_estimado(conn, fazenda_id):
    leituras_fake = [
        LeituraNasaPower(data=dt.date(2024, 1, 1), valores={"T2M": 25.0, "PRECTOTCORR": 3.2}),
        LeituraNasaPower(data=dt.date(2024, 1, 2), valores={"T2M": 26.0}),
    ]
    unidades_fake = {"T2M": "C", "PRECTOTCORR": "mm/day"}

    with patch(
        "app.ingestion.nasa_power.nasa_power_client.serie_diaria",
        return_value=(leituras_fake, unidades_fake),
    ):
        resultado = nasa_power_ingestion.ingerir_observacoes(str(fazenda_id))

    assert resultado["linhas_afetadas"] == 3

    obs_tbl = get_table("observacao_meteorologica")
    est_tbl = get_table("estacao_meteorologica")
    estacao = conn.execute(
        select(est_tbl).where(est_tbl.c.codigo_externo == f"FAZENDA:{fazenda_id}")
    ).first()
    linhas = conn.execute(select(obs_tbl).where(obs_tbl.c.estacao_id == estacao.id)).fetchall()
    assert len(linhas) == 3
    assert all(linha.status == db_enums.STATUS_ESTIMADO for linha in linhas)
    unidades_gravadas = {linha.unidade for linha in linhas}
    assert unidades_gravadas == {"C", "mm/day"}
