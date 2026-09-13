"""Client HTTP para a API publica do NASA POWER (sem autenticacao).

Baseado na documentacao/exemplos publicos do endpoint diario por ponto
(power.larc.nasa.gov/docs/services/api/temporal/daily/). Nao validado com
uma chamada real nesta sessao — mesmo bloqueio de rede do client INMET (ver
docs/specs da Fase 2, secao "Riscos") — mas a estrutura de resposta do NASA
POWER (`properties.parameter`, `parameters.<param>.units`) e publicamente
documentada e mais estavel do que a do INMET, entao a confianca aqui e
maior. Confirmar com uma chamada real antes de considerar pronto.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import httpx

from app.clients.http import get_com_retry, novo_client
from app.config import get_settings

COMMUNITY = "AG"  # Agroclimatology — comunidade mais adequada ao domínio
VALOR_AUSENTE = -999.0  # sentinela de dado ausente usada pelo NASA POWER

PARAMETROS_PADRAO = ["PRECTOTCORR", "T2M", "RH2M", "ALLSKY_SFC_SW_DWN", "WS2M"]


class NasaPowerFormatoInesperadoError(RuntimeError):
    """Resposta do NASA POWER nao tem a estrutura esperada (`properties.parameter`)."""


@dataclass(frozen=True)
class LeituraNasaPower:
    data: dt.date
    valores: dict[str, float]  # chave = nome do parametro NASA POWER (ex.: "T2M")


def serie_diaria(
    latitude: float,
    longitude: float,
    inicio: dt.date,
    fim: dt.date,
    parametros: list[str] | None = None,
    client: httpx.Client | None = None,
) -> tuple[list[LeituraNasaPower], dict[str, str]]:
    """Retorna (leituras diarias, unidade por parametro).

    A unidade de cada parametro vem do proprio metadado da resposta
    (`parameters.<param>.units`) — nunca fixada no codigo, para nao arriscar
    gravar uma unidade errada.
    """
    settings = get_settings()
    parametros = parametros or PARAMETROS_PADRAO
    proprio_client = client is None
    client = client or novo_client()
    try:
        params = {
            "parameters": ",".join(parametros),
            "community": COMMUNITY,
            "latitude": f"{latitude:.6f}",
            "longitude": f"{longitude:.6f}",
            "start": inicio.strftime("%Y%m%d"),
            "end": fim.strftime("%Y%m%d"),
            "format": "JSON",
        }
        resposta = get_com_retry(client, settings.nasa_power_base_url, params=params)
        dados = resposta.json()
        try:
            valores_por_parametro: dict[str, dict[str, float]] = dados["properties"]["parameter"]
        except (KeyError, TypeError) as exc:
            raise NasaPowerFormatoInesperadoError(
                f"Resposta do NASA POWER sem 'properties.parameter'. Corpo bruto: {dados!r}"
            ) from exc

        unidades: dict[str, str] = {}
        for parametro in parametros:
            info = dados.get("parameters", {}).get(parametro, {})
            unidades[parametro] = info.get("units", "desconhecida")

        datas: set[str] = set()
        for serie in valores_por_parametro.values():
            datas.update(serie.keys())

        leituras: list[LeituraNasaPower] = []
        for data_str in sorted(datas):
            try:
                data = dt.datetime.strptime(data_str, "%Y%m%d").date()
            except ValueError:
                continue  # chave que nao e uma data (ex.: metadado extra) — ignora
            valores: dict[str, float] = {}
            for parametro, serie in valores_por_parametro.items():
                valor = serie.get(data_str)
                if valor is None or abs(valor - VALOR_AUSENTE) < 0.5:
                    continue  # gap real (sentinela -999) — nunca preenchido
                valores[parametro] = float(valor)
            leituras.append(LeituraNasaPower(data=data, valores=valores))
        return leituras, unidades
    finally:
        if proprio_client:
            client.close()
