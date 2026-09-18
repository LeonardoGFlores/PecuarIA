"""Testes de app.analysis.tendencia — funcoes puras, sem banco/rede."""

from __future__ import annotations

import datetime as dt

import pytest

from app import db_enums
from app.analysis.tendencia import (
    calcular_inclinacao,
    calcular_tendencia,
    calcular_variacao_pct,
    classificar_tendencia,
)

AMOSTRAS_MINIMAS = 5
LIMIAR_VARIACAO_PCT = 10.0
AMOSTRAS_MINIMAS_SAZONAL = 3


def _serie(valores: list[float], inicio: dt.date = dt.date(2024, 6, 1)) -> list[tuple[dt.datetime, float]]:
    return [
        (dt.datetime.combine(inicio + dt.timedelta(days=indice * 5), dt.time(12, 0), tzinfo=dt.timezone.utc), valor)
        for indice, valor in enumerate(valores)
    ]


def test_calcular_inclinacao_serie_crescente():
    pontos = [(0.0, 0.5), (10.0, 0.6), (20.0, 0.7)]
    assert calcular_inclinacao(pontos) == pytest.approx(0.01)


def test_calcular_inclinacao_serie_decrescente():
    pontos = [(0.0, 0.7), (10.0, 0.6), (20.0, 0.5)]
    assert calcular_inclinacao(pontos) == pytest.approx(-0.01)


def test_calcular_inclinacao_menos_de_dois_pontos_retorna_zero():
    assert calcular_inclinacao([(0.0, 0.5)]) == 0.0
    assert calcular_inclinacao([]) == 0.0


def test_calcular_variacao_pct_valor_conhecido():
    assert calcular_variacao_pct(0.5, 0.6) == pytest.approx(20.0)
    assert calcular_variacao_pct(0.5, 0.4) == pytest.approx(-20.0)


def test_calcular_variacao_pct_referencia_proxima_de_zero_retorna_none():
    assert calcular_variacao_pct(0.0, 0.5) is None
    assert calcular_variacao_pct(1e-8, 0.5) is None


def test_classificar_tendencia_queda_estavel_alta():
    assert classificar_tendencia(-15.0, LIMIAR_VARIACAO_PCT) == db_enums.CLASSIFICACAO_TENDENCIA_QUEDA
    assert classificar_tendencia(-5.0, LIMIAR_VARIACAO_PCT) == db_enums.CLASSIFICACAO_TENDENCIA_ESTAVEL
    assert classificar_tendencia(15.0, LIMIAR_VARIACAO_PCT) == db_enums.CLASSIFICACAO_TENDENCIA_ALTA
    assert classificar_tendencia(None, LIMIAR_VARIACAO_PCT) == db_enums.CLASSIFICACAO_TENDENCIA_DADOS_INSUFICIENTES


def test_classificar_tendencia_exatamente_no_limiar_conta_como_extremo():
    assert classificar_tendencia(-10.0, LIMIAR_VARIACAO_PCT) == db_enums.CLASSIFICACAO_TENDENCIA_QUEDA
    assert classificar_tendencia(10.0, LIMIAR_VARIACAO_PCT) == db_enums.CLASSIFICACAO_TENDENCIA_ALTA


def test_calcular_tendencia_amostras_insuficientes_gera_dados_insuficientes():
    # Caso de borda obrigatorio (docs/specs/04): janela sem amostras
    # suficientes -> DADOS_INSUFICIENTES, campos numericos None (nunca 0).
    amostras = _serie([0.5, 0.6])  # so 2, abaixo do minimo de 5
    resultado = calcular_tendencia(amostras, [], AMOSTRAS_MINIMAS, LIMIAR_VARIACAO_PCT, AMOSTRAS_MINIMAS_SAZONAL)

    assert resultado.classificacao == db_enums.CLASSIFICACAO_TENDENCIA_DADOS_INSUFICIENTES
    assert resultado.valor_medio_periodo is None
    assert resultado.inclinacao_diaria is None
    assert resultado.variacao_pct_periodo is None
    assert resultado.amostras_periodo == 2
    assert resultado.comparacao_sazonal_disponivel is False


def test_calcular_tendencia_queda_classificada_corretamente():
    amostras = _serie([0.8, 0.7, 0.6, 0.5, 0.4, 0.3])
    resultado = calcular_tendencia(amostras, [], AMOSTRAS_MINIMAS, LIMIAR_VARIACAO_PCT, AMOSTRAS_MINIMAS_SAZONAL)

    assert resultado.amostras_periodo == 6
    assert resultado.classificacao == db_enums.CLASSIFICACAO_TENDENCIA_QUEDA
    assert resultado.inclinacao_diaria < 0
    assert resultado.variacao_pct_periodo == pytest.approx(-62.5)


def test_calcular_tendencia_alta_classificada_corretamente():
    amostras = _serie([0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
    resultado = calcular_tendencia(amostras, [], AMOSTRAS_MINIMAS, LIMIAR_VARIACAO_PCT, AMOSTRAS_MINIMAS_SAZONAL)

    assert resultado.classificacao == db_enums.CLASSIFICACAO_TENDENCIA_ALTA
    assert resultado.inclinacao_diaria > 0


def test_calcular_tendencia_estavel_quando_variacao_pequena():
    amostras = _serie([0.60, 0.61, 0.60, 0.59, 0.60, 0.61])
    resultado = calcular_tendencia(amostras, [], AMOSTRAS_MINIMAS, LIMIAR_VARIACAO_PCT, AMOSTRAS_MINIMAS_SAZONAL)

    assert resultado.classificacao == db_enums.CLASSIFICACAO_TENDENCIA_ESTAVEL


def test_calcular_tendencia_sem_historico_do_ano_anterior_marca_indisponivel():
    # Caso de borda obrigatorio: area sem historico do ano anterior ->
    # comparacao_sazonal_disponivel=false, campos sazonais None.
    amostras = _serie([0.5, 0.55, 0.6, 0.65, 0.7, 0.75])
    resultado = calcular_tendencia(amostras, [], AMOSTRAS_MINIMAS, LIMIAR_VARIACAO_PCT, AMOSTRAS_MINIMAS_SAZONAL)

    assert resultado.comparacao_sazonal_disponivel is False
    assert resultado.valor_medio_periodo_anterior is None
    assert resultado.variacao_sazonal_pct is None
    assert resultado.amostras_periodo_anterior == 0


def test_calcular_tendencia_com_historico_sazonal_suficiente():
    amostras = _serie([0.5, 0.55, 0.6, 0.65, 0.7, 0.75])
    amostras_ano_anterior = _serie([0.4, 0.42, 0.44, 0.46], inicio=dt.date(2023, 6, 1))
    resultado = calcular_tendencia(
        amostras, amostras_ano_anterior, AMOSTRAS_MINIMAS, LIMIAR_VARIACAO_PCT, AMOSTRAS_MINIMAS_SAZONAL
    )

    assert resultado.comparacao_sazonal_disponivel is True
    assert resultado.amostras_periodo_anterior == 4
    assert resultado.valor_medio_periodo_anterior == pytest.approx(0.43, abs=1e-6)
    assert resultado.variacao_sazonal_pct is not None
    assert resultado.variacao_sazonal_pct > 0  # periodo atual mais alto que o anterior


def test_calcular_tendencia_amostras_sazonais_abaixo_do_minimo_fica_indisponivel():
    amostras = _serie([0.5, 0.55, 0.6, 0.65, 0.7, 0.75])
    amostras_ano_anterior = _serie([0.4, 0.42], inicio=dt.date(2023, 6, 1))  # so 2, abaixo do minimo de 3
    resultado = calcular_tendencia(
        amostras, amostras_ano_anterior, AMOSTRAS_MINIMAS, LIMIAR_VARIACAO_PCT, AMOSTRAS_MINIMAS_SAZONAL
    )

    assert resultado.comparacao_sazonal_disponivel is False
    assert resultado.valor_medio_periodo_anterior is None
    assert resultado.variacao_sazonal_pct is None
    assert resultado.amostras_periodo_anterior == 2


def test_calcular_tendencia_ordena_amostras_fora_de_ordem():
    amostras = _serie([0.8, 0.7, 0.6, 0.5, 0.4, 0.3])
    embaralhadas = [amostras[3], amostras[0], amostras[5], amostras[1], amostras[4], amostras[2]]
    resultado_ordenado = calcular_tendencia(
        amostras, [], AMOSTRAS_MINIMAS, LIMIAR_VARIACAO_PCT, AMOSTRAS_MINIMAS_SAZONAL
    )
    resultado_embaralhado = calcular_tendencia(
        embaralhadas, [], AMOSTRAS_MINIMAS, LIMIAR_VARIACAO_PCT, AMOSTRAS_MINIMAS_SAZONAL
    )

    assert resultado_ordenado == resultado_embaralhado
