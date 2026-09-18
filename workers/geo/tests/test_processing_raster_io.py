"""Testes de raster_io.py com GeoTIFFs sinteticos gerados localmente via
rasterio+numpy — sem rede (nenhum COG real e baixado). Cobre recorte,
escala/offset, alinhamento SCL->10m, e os casos de borda obrigatorios de
mascaramento (nuvem cobrindo 100% da area; cena cobrindo so parte dela).
"""

from __future__ import annotations

import numpy as np
import pytest
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_origin
from rasterio.warp import transform_geom
from shapely.geometry import box, mapping

from app.processing.raster_io import (
    caminho_gdal,
    gerar_geotiff_banda_unica_bytes,
    recortar_cena_para_area,
)

CRS_UTM = CRS.from_epsg(32723)  # UTM 23S — arbitrario, so para compor um raster sintetico valido
ORIGEM_X = 500_000.0
ORIGEM_Y = 8_000_000.0
PIXEL_10M = 10.0
PIXEL_20M = 20.0
TAMANHO_10M = 20  # grade 20x20 -> 200x200m
TAMANHO_20M = TAMANHO_10M // 2

ESCALAS_OFFSETS_PADRAO = {
    "red": (1 / 10000, 0.0),
    "nir": (1 / 10000, 0.0),
    "blue": (1 / 10000, 0.0),
}


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


def _geometria_area_4326(fracao_da_extensao: float = 1.0) -> dict:
    """Poligono cobrindo uma fracao central da extensao do raster sintetico,
    construido no UTM e reprojetado para 4326 (round-trip real via PROJ) —
    o formato que `recortar_cena_para_area` espera receber."""
    largura_total = TAMANHO_10M * PIXEL_10M
    altura_total = TAMANHO_10M * PIXEL_10M
    margem = (1 - fracao_da_extensao) / 2
    minx = ORIGEM_X + margem * largura_total
    maxx = ORIGEM_X + (1 - margem) * largura_total
    maxy = ORIGEM_Y - margem * altura_total
    miny = ORIGEM_Y - (1 - margem) * altura_total
    poligono_utm = box(minx, miny, maxx, maxy)
    return transform_geom(CRS_UTM, "EPSG:4326", mapping(poligono_utm))


@pytest.fixture
def cena_uniforme(tmp_path):
    """Cena inteira valida: red/nir/blue com valores DN constantes, SCL
    classe 4 (vegetacao, valida) em toda a extensao."""
    red = np.full((TAMANHO_10M, TAMANHO_10M), 1000, dtype="uint16")  # reflectancia 0.1
    nir = np.full((TAMANHO_10M, TAMANHO_10M), 5000, dtype="uint16")  # reflectancia 0.5
    blue = np.full((TAMANHO_10M, TAMANHO_10M), 500, dtype="uint16")  # reflectancia 0.05
    scl = np.full((TAMANHO_20M, TAMANHO_20M), 4, dtype="uint8")

    _escrever_raster(tmp_path / "red.tif", red, PIXEL_10M, nodata=0, dtype="uint16")
    _escrever_raster(tmp_path / "nir.tif", nir, PIXEL_10M, nodata=0, dtype="uint16")
    _escrever_raster(tmp_path / "blue.tif", blue, PIXEL_10M, nodata=0, dtype="uint16")
    _escrever_raster(tmp_path / "scl.tif", scl, PIXEL_20M, nodata=0, dtype="uint8")

    return {
        "red": str(tmp_path / "red.tif"),
        "nir": str(tmp_path / "nir.tif"),
        "blue": str(tmp_path / "blue.tif"),
        "scl": str(tmp_path / "scl.tif"),
    }


def test_recorta_e_aplica_escala_offset_antes_de_qualquer_calculo(cena_uniforme):
    geometria_area = _geometria_area_4326(fracao_da_extensao=0.5)

    recorte = recortar_cena_para_area(cena_uniforme, ESCALAS_OFFSETS_PADRAO, geometria_area)

    assert recorte.red.count() > 0
    np.testing.assert_allclose(recorte.red.compressed(), 0.1, rtol=1e-6)
    np.testing.assert_allclose(recorte.nir.compressed(), 0.5, rtol=1e-6)
    np.testing.assert_allclose(recorte.blue.compressed(), 0.05, rtol=1e-6)
    # SCL classe 4 e valida em toda a cena -> nada alem da area e mascarado.
    assert recorte.pixels_area_intersecao_cena == recorte.red.count()


def test_area_100pct_coberta_por_nuvem_zera_pixels_validos(tmp_path):
    # Caso de borda obrigatorio (docs/specs/02): toda a area cai em SCL
    # invalido (classe 9 = nuvem alta probabilidade) -> zero pixels
    # validos, mas o denominador (pixels_area_intersecao_cena) continua > 0.
    red = np.full((TAMANHO_10M, TAMANHO_10M), 1000, dtype="uint16")
    nir = np.full((TAMANHO_10M, TAMANHO_10M), 5000, dtype="uint16")
    blue = np.full((TAMANHO_10M, TAMANHO_10M), 500, dtype="uint16")
    scl = np.full((TAMANHO_20M, TAMANHO_20M), 9, dtype="uint8")  # nuvem alta probabilidade

    _escrever_raster(tmp_path / "red.tif", red, PIXEL_10M, nodata=0, dtype="uint16")
    _escrever_raster(tmp_path / "nir.tif", nir, PIXEL_10M, nodata=0, dtype="uint16")
    _escrever_raster(tmp_path / "blue.tif", blue, PIXEL_10M, nodata=0, dtype="uint16")
    _escrever_raster(tmp_path / "scl.tif", scl, PIXEL_20M, nodata=0, dtype="uint8")

    hrefs = {
        "red": str(tmp_path / "red.tif"),
        "nir": str(tmp_path / "nir.tif"),
        "blue": str(tmp_path / "blue.tif"),
        "scl": str(tmp_path / "scl.tif"),
    }
    geometria_area = _geometria_area_4326(fracao_da_extensao=0.5)

    recorte = recortar_cena_para_area(hrefs, ESCALAS_OFFSETS_PADRAO, geometria_area)

    assert recorte.red.count() == 0
    assert recorte.pixels_area_intersecao_cena > 0


def test_cena_cobre_so_parte_da_area_denominador_e_a_intersecao(tmp_path):
    # Caso de borda obrigatorio: metade esquerda do raster e nodata
    # (fora do footprint real da cena) -> pixels_area_intersecao_cena conta
    # so a metade com dado real, mesmo com a area cobrindo a extensao toda.
    red = np.full((TAMANHO_10M, TAMANHO_10M), 1000, dtype="uint16")
    red[:, : TAMANHO_10M // 2] = 0  # nodata na metade esquerda
    nir = np.full((TAMANHO_10M, TAMANHO_10M), 5000, dtype="uint16")
    nir[:, : TAMANHO_10M // 2] = 0
    blue = np.full((TAMANHO_10M, TAMANHO_10M), 500, dtype="uint16")
    blue[:, : TAMANHO_10M // 2] = 0
    scl = np.full((TAMANHO_20M, TAMANHO_20M), 4, dtype="uint8")

    _escrever_raster(tmp_path / "red.tif", red, PIXEL_10M, nodata=0, dtype="uint16")
    _escrever_raster(tmp_path / "nir.tif", nir, PIXEL_10M, nodata=0, dtype="uint16")
    _escrever_raster(tmp_path / "blue.tif", blue, PIXEL_10M, nodata=0, dtype="uint16")
    _escrever_raster(tmp_path / "scl.tif", scl, PIXEL_20M, nodata=0, dtype="uint8")

    hrefs = {
        "red": str(tmp_path / "red.tif"),
        "nir": str(tmp_path / "nir.tif"),
        "blue": str(tmp_path / "blue.tif"),
        "scl": str(tmp_path / "scl.tif"),
    }
    geometria_area = _geometria_area_4326(fracao_da_extensao=1.0)

    recorte = recortar_cena_para_area(hrefs, ESCALAS_OFFSETS_PADRAO, geometria_area)

    total_pixels = TAMANHO_10M * TAMANHO_10M
    assert recorte.pixels_area_intersecao_cena == pytest.approx(total_pixels / 2, abs=TAMANHO_10M)
    assert recorte.pixels_area_intersecao_cena < total_pixels
    # todos os pixels com dado real (metade direita) sao validos (SCL classe 4)
    assert recorte.red.count() == recorte.pixels_area_intersecao_cena


def test_caminho_gdal_normaliza_apenas_urls_http():
    assert caminho_gdal("https://s3.example/B04.tif") == "/vsicurl/https://s3.example/B04.tif"
    assert caminho_gdal("http://s3.example/B04.tif") == "/vsicurl/http://s3.example/B04.tif"
    assert caminho_gdal("/tmp/local/B04.tif") == "/tmp/local/B04.tif"


def test_gerar_geotiff_banda_unica_bytes_roundtrip_com_nodata_nan():
    dados = np.ma.masked_array(
        np.array([[0.5, 0.6], [0.7, 0.8]], dtype="float32"),
        mask=[[False, True], [False, False]],
    )
    transform = from_origin(ORIGEM_X, ORIGEM_Y, PIXEL_10M, PIXEL_10M)

    conteudo = gerar_geotiff_banda_unica_bytes(dados, transform, CRS_UTM)

    with rasterio.io.MemoryFile(conteudo) as memfile:
        with memfile.open() as dataset:
            assert dataset.count == 1
            assert np.isnan(dataset.nodata)
            lido = dataset.read(1)
            assert lido[0, 0] == pytest.approx(0.5)
            assert np.isnan(lido[0, 1])  # pixel mascarado -> NaN, nunca 0
            assert lido[1, 0] == pytest.approx(0.7)
