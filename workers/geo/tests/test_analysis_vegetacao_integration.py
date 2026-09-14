"""Testes de integracao de app.analysis.vegetacao contra Postgres real —
upsert por (area_produtiva_id, tipo) e o registro no manifesto sao
especificos do dialeto/tabela. Pulados se DATABASE_URL nao estiver
acessivel."""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from app import db_enums
from app.analysis.vegetacao import AreaNaoEncontradaError, calcular_tendencia_area
from app.db import get_engine, get_table


@pytest.fixture
def conn():
    try:
        connection = get_engine().connect()
    except OperationalError:
        pytest.skip("Postgres local nao acessivel via DATABASE_URL")
    yield connection
    connection.close()


@pytest.fixture
def area_com_serie(conn):
    """Fazenda + area_produtiva + cena_satelite + indice_vegetacao_area
    (NDVI) cobrindo os ultimos 90 dias (tendencia de queda clara) e o mesmo
    periodo do ano anterior (para a comparacao sazonal)."""
    fazenda_tbl = get_table("fazenda")
    area_tbl = get_table("area_produtiva")
    cena_tbl = get_table("cena_satelite")
    indice_tbl = get_table("indice_vegetacao_area")

    fazenda_id = uuid.uuid4()
    conn.execute(
        fazenda_tbl.insert().values(
            id=fazenda_id,
            nome="Fazenda Teste Tendencia",
            geom="SRID=4326;POLYGON((-47 -15, -47 -15.01, -46.99 -15.01, -46.99 -15, -47 -15))",
            fonte="teste_automatizado",
            status="DECLARADO",
            qualidade="MEDIA",
            versao=1,
        )
    )
    area_id = uuid.uuid4()
    conn.execute(
        area_tbl.insert().values(
            id=area_id,
            fazenda_id=fazenda_id,
            nome="Area Teste Tendencia",
            geom="SRID=4326;POLYGON((-47 -15, -47 -15.01, -46.99 -15.01, -46.99 -15, -47 -15))",
            tipo_uso="PASTO",
            sistema_produtivo="NAO_DEFINIDO",
            fonte="teste_automatizado",
            status="DECLARADO",
            qualidade="MEDIA",
        )
    )

    agora = dt.datetime.now(dt.timezone.utc)
    cena_ids = []
    linhas_indice = []

    def _adicionar_amostras(datas_valores, sufixo):
        for indice, (data, valor) in enumerate(datas_valores):
            cena_id = uuid.uuid4()
            cena_ids.append(cena_id)
            conn.execute(
                cena_tbl.insert().values(
                    id=cena_id,
                    fonte=db_enums.FONTE_CENA_SENTINEL2_L2A,
                    item_stac_id=f"teste-tendencia-{sufixo}-{indice}-{uuid.uuid4()}",
                    tile_id="23KKQ",
                    data_aquisicao=data,
                    cobertura_nuvem_cena_pct=5.0,
                    geom="SRID=4326;POLYGON((-48 -16, -48 -14, -46 -14, -46 -16, -48 -16))",
                    status_processamento=db_enums.STATUS_CENA_PROCESSADA,
                    ativos={},
                )
            )
            linhas_indice.append(
                {
                    "id": uuid.uuid4(),
                    "area_produtiva_id": area_id,
                    "cena_id": cena_id,
                    "tipo": db_enums.TIPO_INDICE_NDVI,
                    "data_aquisicao": data,
                    "cobertura_valida_pct": 95.0,
                    "mediana": valor,
                    "qualidade": db_enums.QUALIDADE_INDICE_SUFICIENTE,
                    "versao_processamento": "ndvi-evi-v1",
                    "raster_ref": f"ndvi-evi/teste/{sufixo}/{indice}/NDVI.tif",
                }
            )

    # Janela recente (ultimos 80 dias): queda clara de 0.8 para 0.3.
    amostras_recentes = [
        (agora - dt.timedelta(days=dias), valor)
        for dias, valor in zip(range(80, -1, -10), [0.8, 0.72, 0.64, 0.56, 0.48, 0.4, 0.32, 0.3, 0.28])
    ]
    _adicionar_amostras(amostras_recentes, "recente")

    # Mesmo periodo do ano anterior: valores mais baixos (para testar
    # variacao sazonal positiva/negativa de forma verificavel).
    amostras_ano_anterior = [
        (agora - dt.timedelta(days=365 + dias), valor)
        for dias, valor in zip(range(80, -1, -20), [0.2, 0.22, 0.24, 0.26, 0.28])
    ]
    _adicionar_amostras(amostras_ano_anterior, "anterior")

    conn.execute(indice_tbl.insert().values(linhas_indice))
    conn.commit()

    yield fazenda_id, area_id

    tendencia_tbl = get_table("tendencia_vegetacao_area")
    exec_tbl = get_table("execucao_processamento")
    conn.execute(delete(tendencia_tbl).where(tendencia_tbl.c.area_produtiva_id == area_id))
    conn.execute(delete(indice_tbl).where(indice_tbl.c.area_produtiva_id == area_id))
    for cena_id in cena_ids:
        conn.execute(delete(cena_tbl).where(cena_tbl.c.id == cena_id))
    conn.execute(delete(exec_tbl).where(exec_tbl.c.parametros["area_produtiva_id"].astext == str(area_id)))
    conn.execute(delete(area_tbl).where(area_tbl.c.id == area_id))
    conn.execute(delete(fazenda_tbl).where(fazenda_tbl.c.id == fazenda_id))
    conn.commit()


def test_calcular_tendencia_area_grava_queda_e_comparacao_sazonal(conn, area_com_serie):
    _fazenda_id, area_id = area_com_serie

    resultado = calcular_tendencia_area(str(area_id), db_enums.TIPO_INDICE_NDVI)

    assert resultado["classificacao"] == db_enums.CLASSIFICACAO_TENDENCIA_QUEDA
    assert resultado["amostras_periodo"] == 9

    tabela = get_table("tendencia_vegetacao_area")
    linha = conn.execute(
        select(tabela).where(tabela.c.area_produtiva_id == area_id, tabela.c.tipo == db_enums.TIPO_INDICE_NDVI)
    ).first()
    assert linha is not None
    assert linha.classificacao == db_enums.CLASSIFICACAO_TENDENCIA_QUEDA
    assert linha.comparacao_sazonal_disponivel is True
    assert linha.amostras_periodo_anterior == 5
    assert float(linha.variacao_sazonal_pct) > 0  # periodo atual mais alto que o do ano anterior

    exec_tbl = get_table("execucao_processamento")
    execucao = conn.execute(
        select(exec_tbl).where(exec_tbl.c.tipo == db_enums.TIPO_EXECUCAO_TENDENCIA_VEGETACAO)
    ).first()
    assert execucao is not None
    assert execucao.status == db_enums.STATUS_EXECUCAO_SUCESSO


def test_calcular_tendencia_area_e_idempotente_via_upsert(conn, area_com_serie):
    _fazenda_id, area_id = area_com_serie

    calcular_tendencia_area(str(area_id), db_enums.TIPO_INDICE_NDVI)
    calcular_tendencia_area(str(area_id), db_enums.TIPO_INDICE_NDVI)  # roda de novo — nao deve duplicar

    tabela = get_table("tendencia_vegetacao_area")
    linhas = conn.execute(
        select(tabela).where(tabela.c.area_produtiva_id == area_id, tabela.c.tipo == db_enums.TIPO_INDICE_NDVI)
    ).fetchall()
    assert len(linhas) == 1


def test_calcular_tendencia_area_sem_serie_evi_gera_dados_insuficientes(conn, area_com_serie):
    # Mesma area, mas tipo=EVI nao tem nenhuma amostra inserida pelo fixture.
    _fazenda_id, area_id = area_com_serie

    resultado = calcular_tendencia_area(str(area_id), db_enums.TIPO_INDICE_EVI)

    assert resultado["classificacao"] == db_enums.CLASSIFICACAO_TENDENCIA_DADOS_INSUFICIENTES
    assert resultado["amostras_periodo"] == 0

    tabela = get_table("tendencia_vegetacao_area")
    linha = conn.execute(
        select(tabela).where(tabela.c.area_produtiva_id == area_id, tabela.c.tipo == db_enums.TIPO_INDICE_EVI)
    ).first()
    assert linha.valor_medio_periodo is None
    assert linha.inclinacao_diaria is None


def test_calcular_tendencia_area_falha_com_area_inexistente(conn):
    with pytest.raises(AreaNaoEncontradaError):
        calcular_tendencia_area(str(uuid.uuid4()), db_enums.TIPO_INDICE_NDVI)
