"""Testes de integracao do upsert de cena_satelite/indice_vegetacao_area
contra Postgres real — ON CONFLICT e especifico do dialeto. Pulados
automaticamente se DATABASE_URL nao estiver acessivel."""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from app import db_enums
from app.db import get_engine, get_table
from app.ingestion.upsert import upsert_cena_satelite, upsert_indice_vegetacao


@pytest.fixture
def conn():
    try:
        connection = get_engine().connect()
    except OperationalError:
        pytest.skip("Postgres local nao acessivel via DATABASE_URL")
    yield connection
    connection.close()


@pytest.fixture
def area_teste(conn):
    """Cria uma fazenda + area_produtiva descartaveis e limpa no final."""
    fazenda_tbl = get_table("fazenda")
    area_tbl = get_table("area_produtiva")

    fazenda_id = uuid.uuid4()
    conn.execute(
        fazenda_tbl.insert().values(
            id=fazenda_id,
            nome="Fazenda Teste Vegetacao",
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
            nome="Area Teste",
            geom="SRID=4326;POLYGON((-47 -15, -47 -15.01, -46.99 -15.01, -46.99 -15, -47 -15))",
            tipo_uso="PASTO",
            sistema_produtivo="NAO_DEFINIDO",
            fonte="teste_automatizado",
            status="DECLARADO",
            qualidade="MEDIA",
        )
    )
    conn.commit()

    yield fazenda_id, area_id

    cena_tbl = get_table("cena_satelite")
    indice_tbl = get_table("indice_vegetacao_area")
    conn.execute(delete(indice_tbl).where(indice_tbl.c.area_produtiva_id == area_id))
    conn.execute(delete(area_tbl).where(area_tbl.c.id == area_id))
    conn.execute(delete(fazenda_tbl).where(fazenda_tbl.c.id == fazenda_id))
    conn.commit()


@pytest.fixture
def limpar_cenas_por_item_stac_id(conn):
    ids_criados: list[str] = []
    yield ids_criados
    cena_tbl = get_table("cena_satelite")
    for item_stac_id in ids_criados:
        conn.execute(delete(cena_tbl).where(cena_tbl.c.item_stac_id == item_stac_id))
    conn.commit()


def _dados_cena(item_stac_id: str, **overrides) -> dict:
    base = {
        "fonte": db_enums.FONTE_CENA_SENTINEL2_L2A,
        "item_stac_id": item_stac_id,
        "tile_id": "23KKQ",
        "data_aquisicao": dt.datetime(2024, 6, 15, 13, 30, tzinfo=dt.timezone.utc),
        "cobertura_nuvem_cena_pct": 5.0,
        "geom": "SRID=4326;POLYGON((-48 -16, -48 -14, -46 -14, -46 -16, -48 -16))",
        "status_processamento": db_enums.STATUS_CENA_PENDENTE,
        "ativos": {"red": {"href": "https://s3.example/B04.tif"}},
    }
    base.update(overrides)
    return base


def test_upsert_cena_satelite_insere_nova(conn, limpar_cenas_por_item_stac_id):
    item_stac_id = f"teste-{uuid.uuid4()}"
    limpar_cenas_por_item_stac_id.append(item_stac_id)

    cena_id, foi_criada = upsert_cena_satelite(conn, _dados_cena(item_stac_id))

    assert foi_criada is True

    tabela = get_table("cena_satelite")
    linha = conn.execute(select(tabela).where(tabela.c.id == cena_id)).first()
    assert linha.item_stac_id == item_stac_id
    assert linha.status_processamento == db_enums.STATUS_CENA_PENDENTE


def test_upsert_cena_satelite_dedup_entre_fazendas_vizinhas(conn, limpar_cenas_por_item_stac_id):
    # Mesma cena descoberta por duas fazendas vizinhas que compartilham o
    # footprint de ~100x100km -> a segunda chamada nao cria uma nova linha,
    # retorna o id da ja existente.
    item_stac_id = f"teste-{uuid.uuid4()}"
    limpar_cenas_por_item_stac_id.append(item_stac_id)

    cena_id_1, foi_criada_1 = upsert_cena_satelite(conn, _dados_cena(item_stac_id))
    cena_id_2, foi_criada_2 = upsert_cena_satelite(conn, _dados_cena(item_stac_id))

    assert foi_criada_1 is True
    assert foi_criada_2 is False
    assert cena_id_1 == cena_id_2

    tabela = get_table("cena_satelite")
    total = conn.execute(select(tabela).where(tabela.c.item_stac_id == item_stac_id)).fetchall()
    assert len(total) == 1


def test_upsert_indice_vegetacao_insere_e_reprocessa(conn, area_teste, limpar_cenas_por_item_stac_id):
    fazenda_id, area_id = area_teste
    item_stac_id = f"teste-{uuid.uuid4()}"
    limpar_cenas_por_item_stac_id.append(item_stac_id)
    cena_id, _ = upsert_cena_satelite(conn, _dados_cena(item_stac_id))

    linha_base = {
        "area_produtiva_id": area_id,
        "cena_id": cena_id,
        "tipo": db_enums.TIPO_INDICE_NDVI,
        "data_aquisicao": dt.datetime(2024, 6, 15, 13, 30, tzinfo=dt.timezone.utc),
        "cobertura_valida_pct": 95.0,
        "mediana": 0.65,
        "p10": 0.5,
        "p25": 0.6,
        "p75": 0.7,
        "p90": 0.75,
        "desvio_padrao": 0.05,
        "qualidade": db_enums.QUALIDADE_INDICE_SUFICIENTE,
        "versao_processamento": "ndvi-evi-v1",
        "raster_ref": "ndvi-evi/fazenda/area/2024-06-15/cena/ndvi-evi-v1/NDVI.tif",
    }

    afetadas = upsert_indice_vegetacao(conn, [linha_base])
    assert afetadas == 1

    tabela = get_table("indice_vegetacao_area")
    linha = conn.execute(
        select(tabela).where(tabela.c.area_produtiva_id == area_id, tabela.c.cena_id == cena_id)
    ).first()
    assert float(linha.mediana) == pytest.approx(0.65)

    # Reprocessamento (ex.: nova versao do pipeline) atualiza em vez de duplicar.
    linha_reprocessada = {**linha_base, "mediana": 0.7, "versao_processamento": "ndvi-evi-v2"}
    afetadas_2 = upsert_indice_vegetacao(conn, [linha_reprocessada])
    assert afetadas_2 == 1

    total = conn.execute(
        select(tabela).where(tabela.c.area_produtiva_id == area_id, tabela.c.cena_id == cena_id)
    ).fetchall()
    assert len(total) == 1
    assert float(total[0].mediana) == pytest.approx(0.7)
    assert total[0].versao_processamento == "ndvi-evi-v2"


def test_upsert_indice_vegetacao_ndvi_e_evi_sao_linhas_separadas(conn, area_teste, limpar_cenas_por_item_stac_id):
    fazenda_id, area_id = area_teste
    item_stac_id = f"teste-{uuid.uuid4()}"
    limpar_cenas_por_item_stac_id.append(item_stac_id)
    cena_id, _ = upsert_cena_satelite(conn, _dados_cena(item_stac_id))

    def _linha(tipo):
        return {
            "area_produtiva_id": area_id,
            "cena_id": cena_id,
            "tipo": tipo,
            "data_aquisicao": dt.datetime(2024, 6, 15, 13, 30, tzinfo=dt.timezone.utc),
            "cobertura_valida_pct": 90.0,
            "mediana": 0.5,
            "p10": None,
            "p25": None,
            "p75": None,
            "p90": None,
            "desvio_padrao": None,
            "qualidade": db_enums.QUALIDADE_INDICE_SUFICIENTE,
            "versao_processamento": "ndvi-evi-v1",
            "raster_ref": f"ndvi-evi/{tipo}.tif",
        }

    afetadas = upsert_indice_vegetacao(conn, [_linha(db_enums.TIPO_INDICE_NDVI), _linha(db_enums.TIPO_INDICE_EVI)])
    assert afetadas == 2

    tabela = get_table("indice_vegetacao_area")
    total = conn.execute(
        select(tabela).where(tabela.c.area_produtiva_id == area_id, tabela.c.cena_id == cena_id)
    ).fetchall()
    assert {linha.tipo for linha in total} == {db_enums.TIPO_INDICE_NDVI, db_enums.TIPO_INDICE_EVI}
