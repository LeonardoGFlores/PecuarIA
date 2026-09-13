import numpy as np

from app.processing.mascara import (
    CLASSES_SCL_INVALIDAS,
    combinar_mascaras,
    mascara_dentro_da_area,
    mascara_scl_valida,
)


def test_mascara_scl_valida_exclui_apenas_as_classes_invalidas():
    scl = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
    mascara = mascara_scl_valida(scl)

    esperado = np.array([classe not in CLASSES_SCL_INVALIDAS for classe in scl])
    np.testing.assert_array_equal(mascara, esperado)


def test_mascara_scl_valida_nao_exclui_agua_nem_solo_exposto():
    # Classes 5 (solo exposto) e 6 (agua) sao informacao sobre a area, nao
    # ruido de sensor — a spec exige que permanecam no dado bruto.
    scl = np.array([5, 6])
    mascara = mascara_scl_valida(scl)
    assert mascara.all()


def test_mascara_dentro_da_area_inverte_convencao_do_rasterio_mask():
    # rasterio.mask.mask retorna True fora do poligono — a mascara de
    # validade precisa do inverso.
    recorte_area = np.array([True, False, True])
    resultado = mascara_dentro_da_area(recorte_area)
    np.testing.assert_array_equal(resultado, [False, True, False])


def test_combinar_mascaras_e_and_logico():
    a = np.array([True, True, False, False])
    b = np.array([True, False, True, False])
    resultado = combinar_mascaras(a, b)
    np.testing.assert_array_equal(resultado, [True, False, False, False])


def test_combinar_mascaras_tres_entradas():
    a = np.array([True, True, True])
    b = np.array([True, True, False])
    c = np.array([True, False, True])
    resultado = combinar_mascaras(a, b, c)
    np.testing.assert_array_equal(resultado, [True, False, False])


def test_combinar_mascaras_sem_entradas_levanta_erro():
    try:
        combinar_mascaras()
        assert False, "deveria ter levantado ValueError"
    except ValueError:
        pass
