"""Funcoes puras de qualidade de dados meteorologicos (docs/specs da Fase 2,
"Algoritmo de avaliacao de representatividade"). Sem I/O — testaveis com
series sinteticas, sem banco nem rede.
"""

from __future__ import annotations

import statistics

from app import db_enums

# Limites fisicos plausiveis por variavel — fora disso, o valor e suspeito
# independente da distancia estatistica (MAD). Radiacao usa um teto
# provisorio ate a unidade real do NASA POWER/INMET ser confirmada.
LIMITE_FISICO_POR_VARIAVEL: dict[str, tuple[float, float]] = {
    db_enums.VARIAVEL_TEMPERATURA: (-10.0, 50.0),
    db_enums.VARIAVEL_UMIDADE_RELATIVA: (0.0, 100.0),
    db_enums.VARIAVEL_PRECIPITACAO: (0.0, 500.0),
    db_enums.VARIAVEL_VENTO: (0.0, 60.0),
    db_enums.VARIAVEL_RADIACAO: (0.0, 500.0),
}

MAD_MULTIPLICADOR = 5.0


def nivel_completude(dias_com_dado: int, dias_esperados: int) -> str:
    if dias_esperados <= 0:
        return db_enums.NIVEL_INSUFICIENTE
    pct = dias_com_dado / dias_esperados
    if pct >= 0.9:
        return db_enums.NIVEL_BOM
    if pct >= 0.7:
        return db_enums.NIVEL_REGULAR
    return db_enums.NIVEL_INSUFICIENTE


def nivel_atualizacao(idade_dias: float) -> str:
    if idade_dias <= 3:
        return db_enums.NIVEL_BOM
    if idade_dias <= 14:
        return db_enums.NIVEL_REGULAR
    return db_enums.NIVEL_INSUFICIENTE


def nivel_consistencia(pct_suspeitas: float) -> str:
    if pct_suspeitas <= 0.02:
        return db_enums.NIVEL_BOM
    if pct_suspeitas <= 0.10:
        return db_enums.NIVEL_REGULAR
    return db_enums.NIVEL_INSUFICIENTE


def calcular_mediana_e_mad(valores: list[float]) -> tuple[float, float]:
    mediana = statistics.median(valores)
    mad = statistics.median(abs(v - mediana) for v in valores)
    return mediana, mad


def eh_valor_suspeito(valor: float, variavel: str, mediana: float, mad: float) -> bool:
    """Fora do limite fisico plausivel da variavel OU |valor - mediana| > 5*MAD."""
    limite = LIMITE_FISICO_POR_VARIAVEL.get(variavel)
    if limite is not None and not (limite[0] <= valor <= limite[1]):
        return True
    if mad == 0:
        return False  # serie constante nesta janela — nao ha o que comparar estatisticamente
    return abs(valor - mediana) > MAD_MULTIPLICADOR * mad


def marcar_suspeitos(valores: list[float], variavel: str) -> list[bool]:
    """Mascara booleana (mesma ordem de `valores`) indicando quais sao suspeitos."""
    if not valores:
        return []
    mediana, mad = calcular_mediana_e_mad(valores)
    return [eh_valor_suspeito(v, variavel, mediana, mad) for v in valores]
