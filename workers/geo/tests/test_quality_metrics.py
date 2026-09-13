"""Testes de app.quality.metrics — funcoes puras, sem banco/rede."""

import pytest

from app import db_enums
from app.quality import metrics


@pytest.mark.parametrize(
    ("dias_com_dado", "dias_esperados", "esperado"),
    [
        (365, 365, db_enums.NIVEL_BOM),
        (330, 365, db_enums.NIVEL_BOM),  # ~90.4%
        (300, 365, db_enums.NIVEL_REGULAR),  # ~82%
        (256, 365, db_enums.NIVEL_REGULAR),  # ~70.1% -> logo acima da fronteira de 70%
        (100, 365, db_enums.NIVEL_INSUFICIENTE),
        (0, 0, db_enums.NIVEL_INSUFICIENTE),
    ],
)
def test_nivel_completude(dias_com_dado, dias_esperados, esperado):
    assert metrics.nivel_completude(dias_com_dado, dias_esperados) == esperado


@pytest.mark.parametrize(
    ("idade_dias", "esperado"),
    [
        (0, db_enums.NIVEL_BOM),
        (3, db_enums.NIVEL_BOM),
        (3.1, db_enums.NIVEL_REGULAR),
        (14, db_enums.NIVEL_REGULAR),
        (14.1, db_enums.NIVEL_INSUFICIENTE),
        (30, db_enums.NIVEL_INSUFICIENTE),
    ],
)
def test_nivel_atualizacao(idade_dias, esperado):
    assert metrics.nivel_atualizacao(idade_dias) == esperado


@pytest.mark.parametrize(
    ("pct_suspeitas", "esperado"),
    [
        (0.0, db_enums.NIVEL_BOM),
        (0.02, db_enums.NIVEL_BOM),
        (0.05, db_enums.NIVEL_REGULAR),
        (0.10, db_enums.NIVEL_REGULAR),
        (0.11, db_enums.NIVEL_INSUFICIENTE),
    ],
)
def test_nivel_consistencia(pct_suspeitas, esperado):
    assert metrics.nivel_consistencia(pct_suspeitas) == esperado


def test_eh_valor_suspeito_fora_do_limite_fisico():
    # temperatura de 80C esta fora de qualquer limite plausivel, mesmo se a
    # serie ao redor tiver uma mediana/MAD que "aceitaria" estatisticamente
    assert metrics.eh_valor_suspeito(80.0, db_enums.VARIAVEL_TEMPERATURA, mediana=25.0, mad=1.0) is True


def test_eh_valor_suspeito_dentro_do_limite_fisico_mas_fora_do_mad():
    assert metrics.eh_valor_suspeito(40.0, db_enums.VARIAVEL_TEMPERATURA, mediana=25.0, mad=1.0) is True


def test_eh_valor_suspeito_valor_normal_nao_e_suspeito():
    assert metrics.eh_valor_suspeito(26.0, db_enums.VARIAVEL_TEMPERATURA, mediana=25.0, mad=1.0) is False


def test_eh_valor_suspeito_mad_zero_serie_constante_nao_marca():
    assert metrics.eh_valor_suspeito(25.0, db_enums.VARIAVEL_TEMPERATURA, mediana=25.0, mad=0.0) is False


def test_marcar_suspeitos_identifica_outlier_em_serie():
    valores = [25.0, 25.5, 24.8, 25.2, 90.0, 25.1]  # 90.0 e um outlier claro
    mascara = metrics.marcar_suspeitos(valores, db_enums.VARIAVEL_TEMPERATURA)
    assert mascara == [False, False, False, False, True, False]


def test_marcar_suspeitos_lista_vazia():
    assert metrics.marcar_suspeitos([], db_enums.VARIAVEL_TEMPERATURA) == []
