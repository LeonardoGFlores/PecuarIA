"""Testes de integracao das tasks de satelite (descoberta + processamento)
contra Postgres real, GeoTIFFs sinteticos locais (sem rede — os hrefs sao
caminhos locais, que `raster_io.caminho_gdal` deixa passar inalterados) e
um `moto` local para storage. `stac_client.buscar_cenas` e mockado (o STAC
real esta bloqueado nesta sandbox); todo o resto roda com o codigo real.
Pulado se DATABASE_URL nao estiver acessivel.
"""

from __future__ import annotations

import datetime as dt
import uuid
from unittest.mock import patch

import numpy as np
import pytest
import rasterio
from moto.server import ThreadedMotoServer
from rasterio.crs import CRS
from rasterio.transform import from_origin
from rasterio.warp import transform_geom
from shapely.geometry import box, mapping, shape
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from app import db_enums
from app.clients import stac as stac_client
from app.config import get_settings
from app.db import get_engine, get_table
from app.ingestion import sentinel2

CRS_UTM = CRS.from_epsg(32723)
ORIGEM_X = 500_000.0
ORIGEM_Y = 8_000_000.0
PIXEL_10M = 10.0
PIXEL_20M = 20.0
TAMANHO_10M = 20
TAMANHO_20M = TAMANHO_10M // 2


@pytest.fixture
def conn():
    try:
        connection = get_engine().connect()
    except OperationalError:
        pytest.skip("Postgres local nao acessivel via DATABASE_URL")
    yield connection
    connection.close()


@pytest.fixture(scope="module")
def moto_server():
    servidor = ThreadedMotoServer(port=0)
    servidor.start()
    host, port = servidor.get_host_and_port()
    yield f"http://{host}:{port}"
    servidor.stop()


@pytest.fixture
def settings_teste(monkeypatch, moto_server):
    monkeypatch.setenv("STORAGE_ENDPOINT_URL", moto_server)
    monkeypatch.setenv("STORAGE_ACCESS_KEY_ID", "teste")
    monkeypatch.setenv("STORAGE_SECRET_ACCESS_KEY", "teste")
    monkeypatch.setenv("STORAGE_BUCKET", f"pecuaria-teste-{uuid.uuid4().hex[:8]}")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


def _escrever_raster(caminho, dados, pixel_size, nodata, dtype):
    transform = from_origin(ORIGEM_X, ORIGEM_Y, pixel_size, pixel_size)
    perfil = {
        "driver": "GTiff",
        "height": dados.shape[0],
        "width": dados.shape[1],
        "count": 1,
        "dtype": dtype,
        "crs": CRS_UTM,
        "transform": transform,
        "nodata": nodata,
    }
    with rasterio.open(caminho, "w", **perfil) as destino:
        destino.write(dados, 1)


def _geometria_utm_para_4326(poligono_utm) -> dict:
    return transform_geom(CRS_UTM, "EPSG:4326", mapping(poligono_utm))


def _poligono_extensao_total():
    largura_total = TAMANHO_10M * PIXEL_10M
    return box(ORIGEM_X, ORIGEM_Y - largura_total, ORIGEM_X + largura_total, ORIGEM_Y)


def _cena_sintetica(tmp_path, prefixo: str, scl_classe: int = 4) -> dict:
    red = np.full((TAMANHO_10M, TAMANHO_10M), 1000, dtype="uint16")
    nir = np.full((TAMANHO_10M, TAMANHO_10M), 5000, dtype="uint16")
    blue = np.full((TAMANHO_10M, TAMANHO_10M), 500, dtype="uint16")
    scl = np.full((TAMANHO_20M, TAMANHO_20M), scl_classe, dtype="uint8")
    _escrever_raster(tmp_path / f"{prefixo}_red.tif", red, PIXEL_10M, 0, "uint16")
    _escrever_raster(tmp_path / f"{prefixo}_nir.tif", nir, PIXEL_10M, 0, "uint16")
    _escrever_raster(tmp_path / f"{prefixo}_blue.tif", blue, PIXEL_10M, 0, "uint16")
    _escrever_raster(tmp_path / f"{prefixo}_scl.tif", scl, PIXEL_20M, 0, "uint8")
    return {
        "red": {"href": str(tmp_path / f"{prefixo}_red.tif")},
        "nir": {"href": str(tmp_path / f"{prefixo}_nir.tif")},
        "blue": {"href": str(tmp_path / f"{prefixo}_blue.tif")},
        "scl": {"href": str(tmp_path / f"{prefixo}_scl.tif")},
    }


def _item_stac(item_id: str, ativos: dict, geometria: dict, nuvem_pct: float = 5.0, data: str = "2024-06-15T13:30:00Z"):
    return stac_client.ItemSTAC(
        id=item_id,
        data_aquisicao=data,
        cobertura_nuvem_pct=nuvem_pct,
        geometria=geometria,
        ativos=ativos,
        propriedades={"s2:processing_baseline": "05.00"},
    )


@pytest.fixture
def fazenda_e_area(conn):
    fazenda_tbl = get_table("fazenda")
    area_tbl = get_table("area_produtiva")

    geojson_4326 = _geometria_utm_para_4326(_poligono_extensao_total())
    wkt_4326 = shape(geojson_4326).wkt

    fazenda_id = uuid.uuid4()
    conn.execute(
        fazenda_tbl.insert().values(
            id=fazenda_id,
            nome="Fazenda Teste Satelite",
            geom=f"SRID=4326;{wkt_4326}",
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
            geom=f"SRID=4326;{wkt_4326}",
            tipo_uso="PASTO",
            sistema_produtivo="NAO_DEFINIDO",
            fonte="teste_automatizado",
            status="DECLARADO",
            qualidade="MEDIA",
        )
    )
    conn.commit()

    yield fazenda_id, area_id, geojson_4326

    indice_tbl = get_table("indice_vegetacao_area")
    area_tbl_ref = area_tbl
    exec_tbl = get_table("execucao_processamento")
    conn.execute(delete(indice_tbl).where(indice_tbl.c.area_produtiva_id == area_id))
    conn.execute(delete(exec_tbl).where(exec_tbl.c.parametros["area_produtiva_id"].astext == str(area_id)))
    conn.execute(delete(exec_tbl).where(exec_tbl.c.entrada_fontes.any(f"SENTINEL2_L2A:fazenda={fazenda_id}")))
    conn.execute(delete(area_tbl_ref).where(area_tbl_ref.c.id == area_id))
    conn.execute(delete(fazenda_tbl).where(fazenda_tbl.c.id == fazenda_id))
    conn.commit()


@pytest.fixture
def limpar_cena_por_item_stac_id(conn):
    ids_criados: list[str] = []
    yield ids_criados
    cena_tbl = get_table("cena_satelite")
    exec_tbl = get_table("execucao_processamento")
    for item_stac_id in ids_criados:
        cena = conn.execute(select(cena_tbl.c.id).where(cena_tbl.c.item_stac_id == item_stac_id)).first()
        if cena is not None:
            conn.execute(delete(exec_tbl).where(exec_tbl.c.entrada_fontes.any(f"cena_satelite:{cena.id}")))
        conn.execute(delete(cena_tbl).where(cena_tbl.c.item_stac_id == item_stac_id))
    conn.commit()


def test_descobrir_cenas_cria_cena_e_despacha_area_intersectante(
    conn, fazenda_e_area, tmp_path, limpar_cena_por_item_stac_id
):
    fazenda_id, area_id, geojson_4326 = fazenda_e_area
    item_stac_id = f"item-teste-{uuid.uuid4()}"
    limpar_cena_por_item_stac_id.append(item_stac_id)
    ativos = _cena_sintetica(tmp_path, "cena1")
    item = _item_stac(item_stac_id, ativos, geojson_4326, nuvem_pct=5.0)

    with (
        patch("app.ingestion.sentinel2.stac_client.buscar_cenas", return_value=[item]),
        patch("app.ingestion.sentinel2.processar_cena_area.delay") as mock_delay,
    ):
        resultado = sentinel2.descobrir_cenas(str(fazenda_id))

    assert resultado["cenas_novas"] == 1
    assert resultado["areas_despachadas"] == 1
    mock_delay.assert_called_once()

    cena_tbl = get_table("cena_satelite")
    linha = conn.execute(select(cena_tbl).where(cena_tbl.c.item_stac_id == item_stac_id)).first()
    assert linha.status_processamento == db_enums.STATUS_CENA_PENDENTE
    assert set(linha.ativos.keys()) == {"red", "nir", "blue", "scl"}
    assert linha.ativos["red"]["scale"] == pytest.approx(1 / 10000)


def test_descobrir_cenas_rejeita_por_nuvem_e_nao_despacha(
    conn, fazenda_e_area, tmp_path, limpar_cena_por_item_stac_id
):
    fazenda_id, area_id, geojson_4326 = fazenda_e_area
    item_stac_id = f"item-teste-{uuid.uuid4()}"
    limpar_cena_por_item_stac_id.append(item_stac_id)
    ativos = _cena_sintetica(tmp_path, "cena-nublada")
    item = _item_stac(item_stac_id, ativos, geojson_4326, nuvem_pct=95.0)

    with (
        patch("app.ingestion.sentinel2.stac_client.buscar_cenas", return_value=[item]),
        patch("app.ingestion.sentinel2.processar_cena_area.delay") as mock_delay,
    ):
        resultado = sentinel2.descobrir_cenas(str(fazenda_id))

    assert resultado["areas_despachadas"] == 0
    mock_delay.assert_not_called()

    cena_tbl = get_table("cena_satelite")
    linha = conn.execute(select(cena_tbl).where(cena_tbl.c.item_stac_id == item_stac_id)).first()
    assert linha.status_processamento == db_enums.STATUS_CENA_REJEITADA
    assert float(linha.cobertura_nuvem_cena_pct) == pytest.approx(95.0)


def test_processar_cena_area_grava_indices_e_sobe_raster(
    conn, fazenda_e_area, tmp_path, settings_teste, limpar_cena_por_item_stac_id
):
    fazenda_id, area_id, geojson_4326 = fazenda_e_area
    item_stac_id = f"item-teste-{uuid.uuid4()}"
    limpar_cena_por_item_stac_id.append(item_stac_id)
    ativos = _cena_sintetica(tmp_path, "cena-proc")
    item = _item_stac(item_stac_id, ativos, geojson_4326, nuvem_pct=5.0)

    with patch("app.ingestion.sentinel2.stac_client.buscar_cenas", return_value=[item]):
        sentinel2.descobrir_cenas(str(fazenda_id))

    cena_tbl = get_table("cena_satelite")
    cena = conn.execute(select(cena_tbl).where(cena_tbl.c.item_stac_id == item_stac_id)).first()

    resultado = sentinel2.processar_cena_area(str(cena.id), str(area_id))

    assert resultado["status"] == "processada"
    assert resultado["cobertura_ndvi_pct"] == pytest.approx(100.0)

    indice_tbl = get_table("indice_vegetacao_area")
    linhas = conn.execute(
        select(indice_tbl).where(indice_tbl.c.area_produtiva_id == area_id, indice_tbl.c.cena_id == cena.id)
    ).fetchall()
    assert {linha.tipo for linha in linhas} == {db_enums.TIPO_INDICE_NDVI, db_enums.TIPO_INDICE_EVI}
    for linha in linhas:
        assert linha.qualidade == db_enums.QUALIDADE_INDICE_SUFICIENTE
        assert linha.raster_ref.startswith(f"ndvi-evi/{fazenda_id}/{area_id}/")

    cena_atualizada = conn.execute(select(cena_tbl).where(cena_tbl.c.id == cena.id)).first()
    assert cena_atualizada.status_processamento == db_enums.STATUS_CENA_PROCESSADA

    from app.clients import storage as storage_client

    client = storage_client.novo_client_s3()
    settings = get_settings()
    objeto = storage_client.ler_objeto(client, settings.storage_bucket, linhas[0].raster_ref)
    assert len(objeto) > 0


def test_reconciliacao_marca_cena_de_menor_cobertura_como_redundante(
    conn, fazenda_e_area, tmp_path, settings_teste, limpar_cena_por_item_stac_id
):
    fazenda_id, area_id, geojson_4326 = fazenda_e_area

    # Duas cenas cobrindo a MESMA area no MESMO dia — geometrias identicas
    # (mesma_parte=True), mas SCL diferente: cena A 100% valida (cobertura
    # alta), cena B com metade em nuvem (cobertura baixa) -> B fica REDUNDANTE.
    item_a_id = f"item-teste-a-{uuid.uuid4()}"
    item_b_id = f"item-teste-b-{uuid.uuid4()}"
    limpar_cena_por_item_stac_id.extend([item_a_id, item_b_id])

    ativos_a = _cena_sintetica(tmp_path, "cena-a", scl_classe=4)  # 100% valida
    ativos_b = _cena_sintetica(tmp_path, "cena-b", scl_classe=9)  # 100% nuvem -> 0% valida

    item_a = _item_stac(item_a_id, ativos_a, geojson_4326, nuvem_pct=5.0, data="2024-06-15T13:30:00Z")
    item_b = _item_stac(item_b_id, ativos_b, geojson_4326, nuvem_pct=5.0, data="2024-06-15T13:31:00Z")

    with patch("app.ingestion.sentinel2.stac_client.buscar_cenas", return_value=[item_a, item_b]):
        sentinel2.descobrir_cenas(str(fazenda_id))

    cena_tbl = get_table("cena_satelite")
    cena_a = conn.execute(select(cena_tbl).where(cena_tbl.c.item_stac_id == item_a_id)).first()
    cena_b = conn.execute(select(cena_tbl).where(cena_tbl.c.item_stac_id == item_b_id)).first()

    sentinel2.processar_cena_area(str(cena_a.id), str(area_id))
    sentinel2.processar_cena_area(str(cena_b.id), str(area_id))

    cena_a_final = conn.execute(select(cena_tbl).where(cena_tbl.c.id == cena_a.id)).first()
    cena_b_final = conn.execute(select(cena_tbl).where(cena_tbl.c.id == cena_b.id)).first()

    assert cena_a_final.status_processamento == db_enums.STATUS_CENA_PROCESSADA
    assert cena_b_final.status_processamento == db_enums.STATUS_CENA_REDUNDANTE

    # nenhuma linha de indice_vegetacao_area foi apagada — evidencia preservada.
    indice_tbl = get_table("indice_vegetacao_area")
    total = conn.execute(
        select(indice_tbl).where(indice_tbl.c.area_produtiva_id == area_id)
    ).fetchall()
    assert {linha.cena_id for linha in total} == {cena_a.id, cena_b.id}
