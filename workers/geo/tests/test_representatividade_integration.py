"""Testes de integracao da avaliacao de representatividade contra Postgres
real (consulta espacial ST_DWithin e especifica do PostGIS). Pulados se
DATABASE_URL nao estiver acessivel."""

from __future__ import annotations

import datetime as dt
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from app import db_enums
from app.db import get_engine, get_table
from app.ingestion.upsert import upsert_observacoes
from app.quality.representatividade import avaliar_fazenda


@pytest.fixture
def conn():
    try:
        connection = get_engine().connect()
    except OperationalError:
        pytest.skip("Postgres local nao acessivel via DATABASE_URL")
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def mock_nasa_power_delay():
    """Os fixtures deste arquivo so povoam temperatura — as outras 4 variaveis
    ficam sem candidata e acionariam o fallback NASA POWER de verdade
    (`.delay()` manda uma mensagem real pro Redis) em todo teste que nao for
    especificamente sobre esse gatilho. Mock automatico evita vazar mensagens
    reais durante os testes; o teste dedicado ao gatilho usa este mesmo mock."""
    with patch("app.quality.representatividade.nasa_power_ingestion.ingerir_observacoes.delay") as mock_delay:
        yield mock_delay


@pytest.fixture
def cenario(conn):
    """Uma fazenda + 3 estacoes candidatas:
    - `boa`: INMET, perto, dados completos e recentes -> deve virar REFERENCIA.
    - `longe_mas_boa`: INMET, mais longe mas tambem boa -> AUXILIAR (perde no desempate por distancia).
    - `ruim`: INMET, perto, mas sem dados suficientes -> nem REFERENCIA nem AUXILIAR (sem linha).
    """
    fazenda_tbl = get_table("fazenda")
    estacao_tbl = get_table("estacao_meteorologica")

    fazenda_id = uuid.uuid4()
    conn.execute(
        fazenda_tbl.insert().values(
            id=fazenda_id,
            nome="Fazenda Teste Representatividade",
            geom="SRID=4326;POLYGON((-47 -15, -47 -15.01, -46.99 -15.01, -46.99 -15, -47 -15))",
            fonte="teste_automatizado",
            status="DECLARADO",
            qualidade="MEDIA",
            versao=1,
        )
    )

    ids = {}
    for chave, (lon, lat) in {
        "boa": (-47.0, -15.05),
        "longe_mas_boa": (-47.5, -15.5),
        "ruim": (-47.01, -15.02),
    }.items():
        estacao_id = uuid.uuid4()
        conn.execute(
            estacao_tbl.insert().values(
                id=estacao_id,
                fonte=db_enums.FONTE_INMET,
                codigo_externo=f"TESTE-{chave}",
                nome=f"Estacao {chave}",
                geom=f"SRID=4326;POINT({lon} {lat})",
                tipo=db_enums.TIPO_ESTACAO_OBSERVADO,
                variaveis_disponiveis=[],
            )
        )
        ids[chave] = estacao_id
    conn.commit()

    agora = dt.datetime.now(dt.timezone.utc)

    # "boa" e "longe_mas_boa": 350 dos ultimos 365 dias com dado, atualizado ontem
    linhas_boas = []
    for chave in ("boa", "longe_mas_boa"):
        for dias_atras in range(1, 351):
            linhas_boas.append(
                {
                    "estacao_id": ids[chave],
                    "variavel": db_enums.VARIAVEL_TEMPERATURA,
                    "timestamp": agora - dt.timedelta(days=dias_atras),
                    "valor": 25.0,
                    "unidade": "C",
                    "status": db_enums.STATUS_OBSERVADO,
                    "versao_processamento": "teste-v1",
                }
            )
    upsert_observacoes(conn, linhas_boas)

    # "ruim": so 10 dias de dado nos ultimos 365 -> completude insuficiente
    linhas_ruins = [
        {
            "estacao_id": ids["ruim"],
            "variavel": db_enums.VARIAVEL_TEMPERATURA,
            "timestamp": agora - dt.timedelta(days=dias_atras),
            "valor": 24.0,
            "unidade": "C",
            "status": db_enums.STATUS_OBSERVADO,
            "versao_processamento": "teste-v1",
        }
        for dias_atras in range(1, 11)
    ]
    upsert_observacoes(conn, linhas_ruins)

    yield fazenda_id, ids

    obs_tbl = get_table("observacao_meteorologica")
    avaliacao_tbl = get_table("avaliacao_representatividade")
    exec_tbl = get_table("execucao_processamento")
    for estacao_id in ids.values():
        conn.execute(delete(obs_tbl).where(obs_tbl.c.estacao_id == estacao_id))
        conn.execute(delete(avaliacao_tbl).where(avaliacao_tbl.c.estacao_id == estacao_id))
        conn.execute(delete(estacao_tbl).where(estacao_tbl.c.id == estacao_id))
    conn.execute(delete(exec_tbl).where(exec_tbl.c.parametros["fazenda_id"].astext == str(fazenda_id)))
    conn.execute(delete(fazenda_tbl).where(fazenda_tbl.c.id == fazenda_id))
    conn.commit()


def test_avaliar_fazenda_escolhe_referencia_por_proximidade_entre_elegiveis(conn, cenario):
    fazenda_id, ids = cenario

    resultado = avaliar_fazenda(str(fazenda_id))

    assert resultado["candidatas"] == 3

    avaliacao_tbl = get_table("avaliacao_representatividade")
    linhas = {
        linha.estacao_id: linha
        for linha in conn.execute(
            select(avaliacao_tbl).where(avaliacao_tbl.c.fazenda_id == fazenda_id)
        ).fetchall()
    }

    assert linhas[ids["boa"]].papel == db_enums.PAPEL_REFERENCIA
    assert linhas[ids["longe_mas_boa"]].papel == db_enums.PAPEL_AUXILIAR
    assert ids["ruim"] not in linhas  # sem dado suficiente -> nem referencia nem auxiliar

    assert linhas[ids["boa"]].criterio_completude == db_enums.NIVEL_BOM
    assert linhas[ids["boa"]].criterio_atualizacao == db_enums.NIVEL_BOM


def test_avaliar_fazenda_e_idempotente_via_upsert(conn, cenario):
    fazenda_id, ids = cenario

    avaliar_fazenda(str(fazenda_id))
    avaliar_fazenda(str(fazenda_id))  # roda de novo — nao deve duplicar

    avaliacao_tbl = get_table("avaliacao_representatividade")
    linhas = conn.execute(
        select(avaliacao_tbl).where(avaliacao_tbl.c.fazenda_id == fazenda_id)
    ).fetchall()
    # 2 estacoes qualificadas (boa + longe_mas_boa) x 1 variavel com dado (temperatura)
    assert len(linhas) == 2


@pytest.fixture
def fazenda_isolada(conn):
    """Fazenda sem nenhuma estacao INMET num raio de 100km — deve acionar o
    fallback NASA POWER para todas as variaveis."""
    fazenda_tbl = get_table("fazenda")
    fazenda_id = uuid.uuid4()
    conn.execute(
        fazenda_tbl.insert().values(
            id=fazenda_id,
            nome="Fazenda Isolada Teste",
            # Coordenadas bem longe de qualquer estacao criada em outros testes
            geom="SRID=4326;POLYGON((10 10, 10 10.01, 10.01 10.01, 10.01 10, 10 10))",
            fonte="teste_automatizado",
            status="DECLARADO",
            qualidade="MEDIA",
            versao=1,
        )
    )
    conn.commit()
    yield fazenda_id
    conn.execute(delete(fazenda_tbl).where(fazenda_tbl.c.id == fazenda_id))
    conn.commit()


def test_avaliar_fazenda_sem_candidatas_aciona_fallback_nasa_power(conn, fazenda_isolada, mock_nasa_power_delay):
    resultado = avaliar_fazenda(str(fazenda_isolada))

    assert resultado["candidatas"] == 0
    assert resultado["fallback_nasa_power_acionado"] is True
    mock_nasa_power_delay.assert_called_once_with(str(fazenda_isolada))
