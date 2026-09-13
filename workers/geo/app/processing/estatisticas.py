"""Estatisticas agregadas de um indice de vegetacao dentro de uma area
produtiva (docs/specs/02, passos 8-9). Puro numpy — sem I/O de raster.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class EstatisticasIndice:
    cobertura_valida_pct: float
    mediana: float | None
    p10: float | None
    p25: float | None
    p75: float | None
    p90: float | None
    desvio_padrao: float | None
    qualidade_suficiente: bool


def calcular_estatisticas(
    indice: np.ma.MaskedArray,
    pixels_area_intersecao_cena: int,
    limiar_cobertura_valida_minima_pct: float,
) -> EstatisticasIndice:
    """`pixels_area_intersecao_cena` e o total de pixels dentro do poligono
    da area que tambem estao dentro do footprint da cena — denominador da
    cobertura valida (nunca a area inteira nem a cena inteira: ver caso de
    borda "cena cobre so parte do poligono da area" na spec). Pixels fora
    do footprint da cena contam como sem observacao, nao como invalidos —
    por isso nao entram nem no numerador nem no denominador aqui; ja foram
    excluidos de ambos por quem monta esse total (raster_io)."""
    if pixels_area_intersecao_cena <= 0:
        raise ValueError("pixels_area_intersecao_cena deve ser positivo")

    pixels_validos = int(np.ma.count(indice))
    cobertura_valida_pct = round(100.0 * pixels_validos / pixels_area_intersecao_cena, 2)
    qualidade_suficiente = (
        pixels_validos > 0 and cobertura_valida_pct >= limiar_cobertura_valida_minima_pct
    )

    if pixels_validos == 0:
        return EstatisticasIndice(
            cobertura_valida_pct=cobertura_valida_pct,
            mediana=None,
            p10=None,
            p25=None,
            p75=None,
            p90=None,
            desvio_padrao=None,
            qualidade_suficiente=False,
        )

    dados_validos = indice.compressed()
    p10, p25, p75, p90 = np.percentile(dados_validos, [10, 25, 75, 90])

    return EstatisticasIndice(
        cobertura_valida_pct=cobertura_valida_pct,
        mediana=float(np.median(dados_validos)),
        p10=float(p10),
        p25=float(p25),
        p75=float(p75),
        p90=float(p90),
        desvio_padrao=float(np.std(dados_validos)),
        qualidade_suficiente=qualidade_suficiente,
    )
