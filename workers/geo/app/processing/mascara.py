"""Mascara de validade a partir da Scene Classification Layer (SCL) do
Sentinel-2 L2A (docs/specs/02, passo 5). Puro numpy — sem I/O de raster.
"""

from __future__ import annotations

import numpy as np

# Sombra de nuvem (3); nuvem media/alta probabilidade (8, 9); cirrus (10);
# neve/gelo (11). Agua (6) e solo exposto (5) NAO sao mascarados — sao
# informacao sobre a area, nao ruido de sensor (spec, passo 5).
CLASSES_SCL_INVALIDAS = frozenset({3, 8, 9, 10, 11})


def mascara_scl_valida(scl: np.ndarray) -> np.ndarray:
    """Retorna uma mascara booleana (True = pixel valido) a partir da grade
    SCL reamostrada para a resolucao das bandas espectrais (10m)."""
    return ~np.isin(scl, list(CLASSES_SCL_INVALIDAS))


def mascara_dentro_da_area(recorte_area: np.ndarray) -> np.ndarray:
    """`recorte_area` e a mascara booleana produzida por `rasterio.mask.mask`
    (True fora do poligono, seguindo a convencao de masked array do
    rasterio) — inverte para "True = dentro do poligono"."""
    return ~recorte_area


def combinar_mascaras(*mascaras: np.ndarray) -> np.ndarray:
    """Uma mascara final so e valida onde TODAS as mascaras de entrada sao
    validas (AND logico) — usada para combinar SCL, area e footprint da
    cena (docs/specs/02, passo 6)."""
    if not mascaras:
        raise ValueError("combinar_mascaras requer ao menos uma mascara")
    resultado = mascaras[0].copy()
    for mascara in mascaras[1:]:
        resultado &= mascara
    return resultado
