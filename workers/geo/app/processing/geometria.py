"""Classificacao de sobreposicao entre duas cenas do mesmo dia sobre a
mesma area produtiva (docs/specs/02, caso de borda "duas cenas no mesmo
dia"). Opera so em geometrias 4326 (footprint das cenas x poligono da
area), sem qualquer raster — mantem a classificacao testavel com shapely
puro, sem depender do CRS UTM da cena.
"""

from __future__ import annotations

from shapely.geometry.base import BaseGeometry

# Constante de modulo, deliberadamente NAO um dos 3 limiares que a spec
# pede parametrizaveis (nuvem/cobertura/gap) — e um detalhe de
# implementacao da heuristica de reconciliacao, nao um parametro de
# qualidade de dado exposto ao usuario.
LIMIAR_RAZAO_MESMA_PARTE = 0.8


def classificar_sobreposicao(
    area: BaseGeometry, footprint_cena_a: BaseGeometry, footprint_cena_b: BaseGeometry
) -> bool:
    """True se as duas cenas cobrem "a mesma parte" da area (devem ser
    reconciliadas — a de menor cobertura valida marcada redundante); False
    se cobrem "partes diferentes" (ambas ficam, cada uma cobrindo sua
    fatia; a cobertura do dia como uniao e um calculo de leitura, nao
    persistido).

    Razao = area da intersecao das duas interseções (cena_a∩area,
    cena_b∩area) sobre a area da MENOR das duas interseções.
    """
    intersecao_a = area.intersection(footprint_cena_a)
    intersecao_b = area.intersection(footprint_cena_b)

    if intersecao_a.is_empty or intersecao_b.is_empty:
        return False

    intersecao_comum = intersecao_a.intersection(intersecao_b)
    if intersecao_comum.is_empty:
        return False

    menor_area = min(intersecao_a.area, intersecao_b.area)
    if menor_area == 0:
        return False

    razao = intersecao_comum.area / menor_area
    return razao >= LIMIAR_RAZAO_MESMA_PARTE
