"""Calculo de NDVI/EVI sobre reflectancia de superficie ja escalada
(docs/specs/02, passo 7). Opera em `numpy.ma.MaskedArray` — pixels ja
mascarados (nuvem/sombra/fora da area) nunca entram no calculo, e um
denominador proximo de zero e mascarado defensivamente para nao gerar
divisao por zero silenciosa.
"""

from __future__ import annotations

import numpy as np

# EVI: G*(nir-red)/(nir + C1*red - C2*blue + L)
EVI_G = 2.5
EVI_C1 = 6.0
EVI_C2 = 7.5
EVI_L = 1.0

_EPSILON_DENOMINADOR = 1e-6


def calcular_ndvi(red: np.ma.MaskedArray, nir: np.ma.MaskedArray) -> np.ma.MaskedArray:
    denominador = nir + red
    denominador_valido = np.ma.masked_where(np.ma.abs(denominador) < _EPSILON_DENOMINADOR, denominador)
    return (nir - red) / denominador_valido


def calcular_evi(
    red: np.ma.MaskedArray, nir: np.ma.MaskedArray, blue: np.ma.MaskedArray
) -> np.ma.MaskedArray:
    denominador = nir + EVI_C1 * red - EVI_C2 * blue + EVI_L
    denominador_valido = np.ma.masked_where(np.ma.abs(denominador) < _EPSILON_DENOMINADOR, denominador)
    return EVI_G * (nir - red) / denominador_valido
