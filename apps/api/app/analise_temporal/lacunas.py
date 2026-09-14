"""Deteccao de lacunas em uma serie temporal ja filtrada (docs/specs/04,
fluxo B) — calculada na leitura, nunca persistida (o custo de recalculo por
consulta e desprezivel frente ao de manter um cache fresco; ver doc 04).
Puro: opera sobre uma lista de datas, sem banco.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Lacuna:
    periodo_inicio: date
    periodo_fim: date
    dias: int


def detectar_lacunas(datas_validas: list[date], limiar_dias: int, fim_referencia: date) -> list[Lacuna]:
    """Varre `datas_validas` e reporta cada intervalo entre duas
    observacoes consecutivas — ou entre a ultima observacao e
    `fim_referencia` — maior que `limiar_dias`. Nunca preenche o intervalo,
    so o sinaliza (docs/specs/04, P0)."""
    if not datas_validas:
        return []

    datas_ordenadas = sorted(set(datas_validas))
    lacunas: list[Lacuna] = []

    for anterior, atual in zip(datas_ordenadas, datas_ordenadas[1:]):
        dias = (atual - anterior).days
        if dias > limiar_dias:
            lacunas.append(Lacuna(periodo_inicio=anterior, periodo_fim=atual, dias=dias))

    ultima_data = datas_ordenadas[-1]
    dias_desde_ultima = (fim_referencia - ultima_data).days
    if dias_desde_ultima > limiar_dias:
        # Lacuna aberta ate o fim da serie (satelite/estacao sem dado ate
        # agora) — estende ate fim_referencia, nunca so ate a penultima
        # observacao (docs/specs/04, caso de borda).
        lacunas.append(Lacuna(periodo_inicio=ultima_data, periodo_fim=fim_referencia, dias=dias_desde_ultima))

    return lacunas
