"""I/O pesado de raster para o pipeline NDVI/EVI (docs/specs/02, passos
2-6 e 10): abre os assets de uma cena Sentinel-2 L2A (via `/vsicurl/` ou um
caminho local — o que permite testar com GeoTIFFs sinteticos, sem rede),
recorta pela geometria da area produtiva, alinha o SCL (nativo 20m) a grade
de 10m das bandas espectrais, e gera os GeoTIFFs de saida.

Tratamento de CRS: a geometria da area (SRID 4326, pequena) e reprojetada
para o CRS nativo da cena — o raster nunca e reprojetado inteiro, para nao
alterar reflectancia por reamostragem na borda (ver plano da Fase 3).
Recorte via `rasterio.mask.mask`, que o GDAL traduz em range requests HTTP
quando o caminho e `/vsicurl/`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.io import MemoryFile
from rasterio.mask import mask as rasterio_mask
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_geom

from app.processing.mascara import combinar_mascaras, mascara_scl_valida


class RasterAlinhamentoError(RuntimeError):
    """O SCL reamostrado nao ficou alinhado pixel a pixel com as bandas
    espectrais de 10m — sinal de que a suposicao de mesma extensao de tile
    entre bandas de 10m e 20m nao se confirmou para esta cena."""


def caminho_gdal(href: str) -> str:
    """Normaliza um href HTTP(S) para leitura remota via `/vsicurl/`; um
    caminho local (usado nos testes, com GeoTIFFs sinteticos) passa
    inalterado."""
    if href.startswith("http://") or href.startswith("https://"):
        return f"/vsicurl/{href}"
    return href


def reprojetar_geometria_geojson(geometria_geojson: dict, crs_origem: str, crs_destino) -> dict:
    """Reprojeta uma geometria GeoJSON (tipicamente 4326) para o CRS nativo
    da cena — nunca o inverso (o raster nunca e reprojetado)."""
    return transform_geom(crs_origem, crs_destino, geometria_geojson)


@dataclass(frozen=True)
class RecorteCena:
    """Bandas escaladas e mascaradas para uma area, todas alinhadas pixel a
    pixel na grade nativa de 10m da cena. `pixels_area_intersecao_cena` e o
    denominador da cobertura valida: pixels dentro do poligono da area que
    tambem estao dentro do footprint real da cena (antes de qualquer
    mascara de nuvem/sombra do SCL)."""

    red: np.ma.MaskedArray
    nir: np.ma.MaskedArray
    blue: np.ma.MaskedArray
    transform: object
    crs: object
    pixels_area_intersecao_cena: int


def recortar_cena_para_area(
    hrefs: dict[str, str],
    escalas_offsets: dict[str, tuple[float, float]],
    geometria_area_4326: dict,
) -> RecorteCena:
    """Abre red/nir/blue/scl (hrefs ja normalizados por `caminho_gdal`),
    recorta pela area (reprojetada para o CRS da cena) e aplica
    escala/offset nas bandas espectrais ANTES de qualquer calculo
    (docs/specs/02, passo 4). `escalas_offsets` mapeia nome do asset para
    `(scale, offset)`, resolvido previamente por
    `processing.escala.resolver_escala_offset`.
    """
    with (
        rasterio.open(caminho_gdal(hrefs["red"])) as ds_red,
        rasterio.open(caminho_gdal(hrefs["nir"])) as ds_nir,
        rasterio.open(caminho_gdal(hrefs["blue"])) as ds_blue,
        rasterio.open(caminho_gdal(hrefs["scl"])) as ds_scl,
    ):
        crs_cena = ds_red.crs
        geometria_utm = reprojetar_geometria_geojson(geometria_area_4326, "EPSG:4326", crs_cena)

        red_dados, transform_recorte = rasterio_mask(ds_red, [geometria_utm], crop=True, filled=False, indexes=1)
        nir_dados, _ = rasterio_mask(ds_nir, [geometria_utm], crop=True, filled=False, indexes=1)
        blue_dados, _ = rasterio_mask(ds_blue, [geometria_utm], crop=True, filled=False, indexes=1)

        # SCL e nativo em 20m — WarpedVRT o reamostra (nearest, categorico)
        # para a MESMA grade (transform/largura/altura) do red antes do
        # recorte, garantindo que o recorte da VRT produza exatamente a
        # mesma janela/forma do recorte das bandas de 10m.
        with WarpedVRT(
            ds_scl,
            crs=crs_cena,
            transform=ds_red.transform,
            width=ds_red.width,
            height=ds_red.height,
            resampling=Resampling.nearest,
        ) as vrt_scl:
            scl_dados, _ = rasterio_mask(vrt_scl, [geometria_utm], crop=True, filled=False, indexes=1)

    if not (red_dados.shape == nir_dados.shape == blue_dados.shape == scl_dados.shape):
        raise RasterAlinhamentoError(
            f"bandas nao alinhadas apos recorte: red={red_dados.shape} nir={nir_dados.shape} "
            f"blue={blue_dados.shape} scl(reamostrado)={scl_dados.shape}"
        )

    escala_red, offset_red = escalas_offsets["red"]
    escala_nir, offset_nir = escalas_offsets["nir"]
    escala_blue, offset_blue = escalas_offsets["blue"]

    red_reflectancia = red_dados.data.astype("float64") * escala_red + offset_red
    nir_reflectancia = nir_dados.data.astype("float64") * escala_nir + offset_nir
    blue_reflectancia = blue_dados.data.astype("float64") * escala_blue + offset_blue

    # mask=True em rasterio.mask.mask(filled=False) significa "fora do
    # poligono OU nodata da fonte (fora do footprint real da cena)" — ver
    # implementacao de rasterio.mask.mask, que combina os dois com OR.
    dentro_da_area_e_do_footprint = ~(red_dados.mask | nir_dados.mask | blue_dados.mask | scl_dados.mask)
    pixels_area_intersecao_cena = int(np.sum(dentro_da_area_e_do_footprint))

    mascara_scl = mascara_scl_valida(scl_dados.data)
    mascara_final_valida = combinar_mascaras(dentro_da_area_e_do_footprint, mascara_scl)
    mascara_numpy_invalida = ~mascara_final_valida

    return RecorteCena(
        red=np.ma.masked_array(red_reflectancia, mask=mascara_numpy_invalida),
        nir=np.ma.masked_array(nir_reflectancia, mask=mascara_numpy_invalida),
        blue=np.ma.masked_array(blue_reflectancia, mask=mascara_numpy_invalida),
        transform=transform_recorte,
        crs=crs_cena,
        pixels_area_intersecao_cena=pixels_area_intersecao_cena,
    )


def gerar_geotiff_banda_unica_bytes(indice: np.ma.MaskedArray, transform, crs) -> bytes:
    """Serializa um indice (NDVI ou EVI) como GeoTIFF de banda unica em
    memoria (sem tocar disco) — `nodata=NaN`, pixels invalidos gravados
    como NaN, nunca 0 (docs/specs/02, passo 10)."""
    perfil = {
        "driver": "GTiff",
        "height": indice.shape[0],
        "width": indice.shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "nodata": np.nan,
    }
    dados_preenchidos = indice.filled(np.nan).astype("float32")
    with MemoryFile() as memfile:
        with memfile.open(**perfil) as destino:
            destino.write(dados_preenchidos, 1)
        return memfile.read()
