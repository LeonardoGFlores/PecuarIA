import numpy as np
import pytest

from app.processing.estatisticas import calcular_estatisticas

LIMIAR_PADRAO = 60.0


def test_area_100pct_coberta_por_nuvem_gera_qualidade_insuficiente():
    # Caso de borda obrigatorio (docs/specs/02): cobertura_valida_pct=0,
    # sem valores de mediana/percentil (None, nunca 0).
    indice = np.ma.masked_array(np.zeros(10), mask=np.ones(10, dtype=bool))

    resultado = calcular_estatisticas(indice, pixels_area_intersecao_cena=10, limiar_cobertura_valida_minima_pct=LIMIAR_PADRAO)

    assert resultado.cobertura_valida_pct == 0.0
    assert resultado.mediana is None
    assert resultado.p10 is None
    assert resultado.p25 is None
    assert resultado.p75 is None
    assert resultado.p90 is None
    assert resultado.desvio_padrao is None
    assert resultado.qualidade_suficiente is False


def test_cena_cobre_so_parte_da_area_denominador_e_a_intersecao():
    # Caso de borda obrigatorio: pixels fora da cena contam como sem
    # observacao, nao como zero — o denominador passado ja exclui esses
    # pixels (e responsabilidade de quem monta a mascara, nao desta funcao,
    # mas o calculo aqui precisa usar exatamente o denominador recebido).
    dados = np.ma.masked_array([0.5, 0.6, 0.7, 0.8], mask=[False, False, False, False])
    # Area total teria 8 pixels, mas so 4 estao dentro do footprint da cena.
    resultado = calcular_estatisticas(dados, pixels_area_intersecao_cena=4, limiar_cobertura_valida_minima_pct=LIMIAR_PADRAO)

    assert resultado.cobertura_valida_pct == 100.0
    assert resultado.qualidade_suficiente is True
    assert resultado.mediana == pytest.approx(0.65)


def test_cobertura_abaixo_do_limiar_minimo_forca_qualidade_insuficiente():
    # Mesmo com pixels validos e estatisticas calculaveis, cobertura baixa
    # marca qualidade=insuficiente (nao deve ser usada como leitura normal).
    dados = np.ma.masked_array([0.5, 0.6], mask=[False, False])
    resultado = calcular_estatisticas(dados, pixels_area_intersecao_cena=10, limiar_cobertura_valida_minima_pct=LIMIAR_PADRAO)

    assert resultado.cobertura_valida_pct == 20.0
    assert resultado.mediana is not None  # estatisticas ainda sao calculadas...
    assert resultado.qualidade_suficiente is False  # ...mas a leitura fica marcada insuficiente


def test_percentis_e_desvio_padrao_sobre_pixels_validos():
    dados = np.ma.masked_array(
        [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, -999, -999],
        mask=[False] * 10 + [True, True],
    )
    resultado = calcular_estatisticas(dados, pixels_area_intersecao_cena=12, limiar_cobertura_valida_minima_pct=LIMIAR_PADRAO)

    assert resultado.cobertura_valida_pct == pytest.approx(83.33, abs=0.01)
    assert resultado.mediana == pytest.approx(0.55)
    assert resultado.desvio_padrao == pytest.approx(np.std(np.arange(1, 11) / 10))


def test_pixels_area_intersecao_cena_invalido_levanta_erro():
    dados = np.ma.masked_array([0.5], mask=[False])
    with pytest.raises(ValueError):
        calcular_estatisticas(dados, pixels_area_intersecao_cena=0, limiar_cobertura_valida_minima_pct=LIMIAR_PADRAO)
