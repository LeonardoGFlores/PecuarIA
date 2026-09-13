from shapely.geometry import box

from app.processing.geometria import classificar_sobreposicao


def test_duas_cenas_cobrindo_a_mesma_parte_sao_mesma_parte():
    # Caso de borda obrigatorio: duas cenas com footprints quase identicos
    # sobre a mesma area -> "mesma parte" (uma deve virar redundante).
    area = box(0, 0, 10, 10)
    cena_a = box(-5, -5, 12, 12)
    cena_b = box(-5, -5, 11, 11)

    assert classificar_sobreposicao(area, cena_a, cena_b) is True


def test_duas_cenas_cobrindo_partes_diferentes_nao_sao_mesma_parte():
    # Caso de borda obrigatorio: cenas cobrindo metades opostas da area ->
    # "partes diferentes" (ambas ficam, cobertura do dia e a uniao).
    area = box(0, 0, 10, 10)
    cena_a = box(-5, -5, 5, 15)  # metade esquerda
    cena_b = box(5, -5, 15, 15)  # metade direita

    assert classificar_sobreposicao(area, cena_a, cena_b) is False


def test_cena_sem_intersecao_com_a_area_nao_e_mesma_parte():
    area = box(0, 0, 10, 10)
    cena_a = box(-5, -5, 12, 12)
    cena_b = box(100, 100, 110, 110)  # nao toca a area

    assert classificar_sobreposicao(area, cena_a, cena_b) is False


def test_razao_exatamente_no_limiar_e_mesma_parte():
    # area 10x10; cena_a cobre a area inteira; cena_b cobre uma faixa de
    # 8x10 -> intersecao comum = 8x10 = 80, menor intersecao = 80 -> razao 1.0
    area = box(0, 0, 10, 10)
    cena_a = box(-5, -5, 15, 15)
    cena_b = box(-5, -5, 8, 15)

    assert classificar_sobreposicao(area, cena_a, cena_b) is True


def test_razao_abaixo_do_limiar_nao_e_mesma_parte():
    # Duas fatias opostas da area, sem sobreposicao entre si -> intersecao
    # comum vazia -> razao 0, bem abaixo do limiar de 0.8.
    area = box(0, 0, 10, 10)
    cena_b = box(0, 0, 2, 10)
    cena_c = box(8, 0, 10, 10)

    assert classificar_sobreposicao(area, cena_b, cena_c) is False
