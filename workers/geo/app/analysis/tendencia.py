"""Calculo de tendencia recente e comparacao sazonal de uma serie de
indice de vegetacao (docs/specs/04, passos 1-6). Puro — sem I/O de banco.

Sem pandas/numpy.polyfit: a inclinacao por minimos quadrados e uma formula
fechada trivial para as series pequenas envolvidas (dezenas a poucas
centenas de pontos por janela), nao justificando puxar uma dependencia que
a Fase 3 deliberadamente evitou (ver docs/specs/04, lacunas identificadas).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app import db_enums

# Denominador proximo de zero na variacao percentual e tratado como
# indefinido (None) em vez de estourar um valor sem sentido — mesmo
# espirito do epsilon defensivo em processing/indices.py.
_EPSILON_VALOR_REFERENCIA = 1e-6


@dataclass(frozen=True)
class ResultadoTendencia:
    valor_medio_periodo: float | None
    inclinacao_diaria: float | None
    variacao_pct_periodo: float | None
    classificacao: str
    amostras_periodo: int
    comparacao_sazonal_disponivel: bool
    valor_medio_periodo_anterior: float | None
    variacao_sazonal_pct: float | None
    amostras_periodo_anterior: int


def calcular_inclinacao(pontos: list[tuple[float, float]]) -> float:
    """Inclinacao (unidade de y por unidade de x) por minimos quadrados
    fechado sobre pontos `(x, y)` — x tipicamente dias desde o inicio da
    janela, y o valor do indice."""
    n = len(pontos)
    if n < 2:
        return 0.0

    soma_x = sum(x for x, _ in pontos)
    soma_y = sum(y for _, y in pontos)
    soma_xy = sum(x * y for x, y in pontos)
    soma_x2 = sum(x * x for x, _ in pontos)

    denominador = n * soma_x2 - soma_x**2
    if denominador == 0:
        return 0.0
    return (n * soma_xy - soma_x * soma_y) / denominador


def calcular_variacao_pct(valor_referencia: float, valor_atual: float) -> float | None:
    """Variacao percentual de `valor_referencia` para `valor_atual`. `None`
    se a referencia estiver proxima de zero — evita uma variacao percentual
    sem sentido (fisicamente possivel para NDVI/EVI perto de zero)."""
    if abs(valor_referencia) < _EPSILON_VALOR_REFERENCIA:
        return None
    return ((valor_atual - valor_referencia) / abs(valor_referencia)) * 100.0


def classificar_tendencia(variacao_pct: float | None, limiar_pct: float) -> str:
    if variacao_pct is None:
        return db_enums.CLASSIFICACAO_TENDENCIA_DADOS_INSUFICIENTES
    if variacao_pct <= -limiar_pct:
        return db_enums.CLASSIFICACAO_TENDENCIA_QUEDA
    if variacao_pct >= limiar_pct:
        return db_enums.CLASSIFICACAO_TENDENCIA_ALTA
    return db_enums.CLASSIFICACAO_TENDENCIA_ESTAVEL


def calcular_tendencia(
    amostras_periodo: list[tuple[datetime, float]],
    amostras_periodo_anterior: list[tuple[datetime, float]],
    amostras_minimas: int,
    limiar_variacao_pct: float,
    amostras_minimas_sazonal: int,
) -> ResultadoTendencia:
    """Calcula tendencia sobre `amostras_periodo` (janela recente) e, quando
    houver dado suficiente, a comparacao sazonal contra
    `amostras_periodo_anterior` (mesma janela, ano anterior).

    Abaixo de `amostras_minimas` amostras na janela recente, a tendencia
    fica `DADOS_INSUFICIENTES` e todos os campos numericos `None` — nunca
    estimada a partir de poucos pontos (docs/specs/04, caso de borda).
    Abaixo de `amostras_minimas_sazonal` no periodo do ano anterior, a
    comparacao sazonal fica indisponivel (`comparacao_sazonal_disponivel=
    False`), sem afetar a classificacao da tendencia recente.
    """
    n = len(amostras_periodo)
    if n < amostras_minimas:
        return ResultadoTendencia(
            valor_medio_periodo=None,
            inclinacao_diaria=None,
            variacao_pct_periodo=None,
            classificacao=db_enums.CLASSIFICACAO_TENDENCIA_DADOS_INSUFICIENTES,
            amostras_periodo=n,
            comparacao_sazonal_disponivel=False,
            valor_medio_periodo_anterior=None,
            variacao_sazonal_pct=None,
            amostras_periodo_anterior=len(amostras_periodo_anterior),
        )

    amostras_ordenadas = sorted(amostras_periodo, key=lambda item: item[0])
    data_inicial = amostras_ordenadas[0][0]
    pontos = [((data - data_inicial).days, valor) for data, valor in amostras_ordenadas]
    valores = [valor for _, valor in amostras_ordenadas]

    valor_medio = sum(valores) / n
    inclinacao = calcular_inclinacao(pontos)
    variacao_pct = calcular_variacao_pct(amostras_ordenadas[0][1], amostras_ordenadas[-1][1])
    classificacao = classificar_tendencia(variacao_pct, limiar_variacao_pct)

    amostras_anteriores_count = len(amostras_periodo_anterior)
    comparacao_disponivel = amostras_anteriores_count >= amostras_minimas_sazonal
    valor_medio_anterior: float | None = None
    variacao_sazonal: float | None = None
    if comparacao_disponivel:
        valores_anteriores = [valor for _, valor in amostras_periodo_anterior]
        valor_medio_anterior = sum(valores_anteriores) / amostras_anteriores_count
        variacao_sazonal = calcular_variacao_pct(valor_medio_anterior, valor_medio)

    return ResultadoTendencia(
        valor_medio_periodo=valor_medio,
        inclinacao_diaria=inclinacao,
        variacao_pct_periodo=variacao_pct,
        classificacao=classificacao,
        amostras_periodo=n,
        comparacao_sazonal_disponivel=comparacao_disponivel,
        valor_medio_periodo_anterior=valor_medio_anterior,
        variacao_sazonal_pct=variacao_sazonal,
        amostras_periodo_anterior=amostras_anteriores_count,
    )
