"""Testes de app.analise_temporal.lacunas — funcoes puras, sem banco."""

from __future__ import annotations

import datetime as dt

from app.analise_temporal.lacunas import detectar_lacunas


def test_sem_datas_retorna_lista_vazia():
    assert detectar_lacunas([], limiar_dias=15, fim_referencia=dt.date(2024, 6, 1)) == []


def test_serie_sem_gaps_nao_reporta_lacuna():
    datas = [dt.date(2024, 1, 1) + dt.timedelta(days=5 * i) for i in range(10)]
    fim_referencia = datas[-1] + dt.timedelta(days=2)
    assert detectar_lacunas(datas, limiar_dias=15, fim_referencia=fim_referencia) == []


def test_gap_entre_duas_observacoes_e_reportado():
    datas = [dt.date(2024, 1, 1), dt.date(2024, 1, 5), dt.date(2024, 2, 10), dt.date(2024, 2, 15)]
    lacunas = detectar_lacunas(datas, limiar_dias=15, fim_referencia=dt.date(2024, 2, 16))

    assert len(lacunas) == 1
    assert lacunas[0].periodo_inicio == dt.date(2024, 1, 5)
    assert lacunas[0].periodo_fim == dt.date(2024, 2, 10)
    assert lacunas[0].dias == 36


def test_gap_exatamente_no_limiar_nao_conta_como_lacuna():
    datas = [dt.date(2024, 1, 1), dt.date(2024, 1, 16)]  # exatamente 15 dias
    lacunas = detectar_lacunas(datas, limiar_dias=15, fim_referencia=dt.date(2024, 1, 16))
    assert lacunas == []


def test_gap_um_dia_acima_do_limiar_conta_como_lacuna():
    datas = [dt.date(2024, 1, 1), dt.date(2024, 1, 17)]  # 16 dias, acima do limiar de 15
    lacunas = detectar_lacunas(datas, limiar_dias=15, fim_referencia=dt.date(2024, 1, 17))
    assert len(lacunas) == 1
    assert lacunas[0].dias == 16


def test_lacuna_aberta_ate_fim_de_referencia():
    # Caso de borda obrigatorio (docs/specs/04): satelite/estacao sem dado
    # ate agora -> lacuna estende ate fim_referencia, nao so ate a ultima
    # observacao.
    datas = [dt.date(2024, 1, 1), dt.date(2024, 1, 5)]
    fim_referencia = dt.date(2024, 2, 1)  # 27 dias depois da ultima observacao
    lacunas = detectar_lacunas(datas, limiar_dias=15, fim_referencia=fim_referencia)

    assert len(lacunas) == 1
    assert lacunas[0].periodo_inicio == dt.date(2024, 1, 5)
    assert lacunas[0].periodo_fim == fim_referencia
    assert lacunas[0].dias == 27


def test_lacuna_aberta_nao_reportada_se_dentro_do_limiar():
    datas = [dt.date(2024, 1, 1), dt.date(2024, 1, 5)]
    fim_referencia = dt.date(2024, 1, 10)  # so 5 dias depois, abaixo do limiar
    assert detectar_lacunas(datas, limiar_dias=15, fim_referencia=fim_referencia) == []


def test_datas_duplicadas_e_fora_de_ordem_sao_tratadas_corretamente():
    datas = [dt.date(2024, 2, 10), dt.date(2024, 1, 1), dt.date(2024, 1, 1), dt.date(2024, 1, 5)]
    lacunas = detectar_lacunas(datas, limiar_dias=15, fim_referencia=dt.date(2024, 2, 11))

    assert len(lacunas) == 1
    assert lacunas[0].periodo_inicio == dt.date(2024, 1, 5)
    assert lacunas[0].periodo_fim == dt.date(2024, 2, 10)


def test_multiplos_gaps_sao_todos_reportados():
    datas = [dt.date(2024, 1, 1), dt.date(2024, 2, 1), dt.date(2024, 3, 1)]
    lacunas = detectar_lacunas(datas, limiar_dias=15, fim_referencia=dt.date(2024, 3, 1))

    assert len(lacunas) == 2
