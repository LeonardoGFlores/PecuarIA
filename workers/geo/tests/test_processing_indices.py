import numpy as np

from app.processing.indices import calcular_evi, calcular_ndvi


def test_calcular_ndvi_valor_conhecido():
    red = np.ma.masked_array([0.1], mask=[False])
    nir = np.ma.masked_array([0.5], mask=[False])
    resultado = calcular_ndvi(red, nir)
    # (0.5 - 0.1) / (0.5 + 0.1) = 0.6666...
    np.testing.assert_allclose(resultado.data[0], 0.66666667, rtol=1e-6)
    assert not resultado.mask[0]


def test_calcular_ndvi_preserva_mascara_de_entrada():
    red = np.ma.masked_array([0.1, 0.2], mask=[False, True])
    nir = np.ma.masked_array([0.5, 0.3], mask=[False, True])
    resultado = calcular_ndvi(red, nir)
    assert not resultado.mask[0]
    assert resultado.mask[1]


def test_calcular_ndvi_denominador_proximo_de_zero_fica_mascarado():
    # red + nir ~ 0 (fisicamente incomum, mas defensivo contra divisao por
    # zero silenciosa — nunca deve virar inf/nan sem mascara).
    red = np.ma.masked_array([0.0], mask=[False])
    nir = np.ma.masked_array([0.0], mask=[False])
    resultado = calcular_ndvi(red, nir)
    assert resultado.mask[0]


def test_calcular_evi_valor_conhecido():
    red = np.ma.masked_array([0.1], mask=[False])
    nir = np.ma.masked_array([0.5], mask=[False])
    blue = np.ma.masked_array([0.05], mask=[False])
    resultado = calcular_evi(red, nir, blue)
    # 2.5*(0.5-0.1) / (0.5 + 6*0.1 - 7.5*0.05 + 1) = 1.0 / 1.725
    np.testing.assert_allclose(resultado.data[0], 1.0 / 1.725, rtol=1e-6)
    assert not resultado.mask[0]


def test_calcular_evi_preserva_mascara_de_entrada():
    red = np.ma.masked_array([0.1, 0.2], mask=[False, True])
    nir = np.ma.masked_array([0.5, 0.3], mask=[False, True])
    blue = np.ma.masked_array([0.05, 0.1], mask=[False, True])
    resultado = calcular_evi(red, nir, blue)
    assert not resultado.mask[0]
    assert resultado.mask[1]
