"""Client HTTP para a API publica do INMET (sem autenticacao).

ATENCAO — nomes de campo NAO confirmados contra a API real: o proxy de
rede do ambiente onde este codigo foi escrito bloqueia acesso a
apitempo.inmet.gov.br (ver docs/specs da Fase 2, secao "Riscos"). Origem de
cada suposicao:

- Campos do catalogo de estacoes (`/estacoes/T`): SEM exemplo real —
  convencao especulativa baseada em nomenclatura comum do INMET
  (`CD_`/`DC_`/`VL_`). Alta chance de precisar correcao.
- Campos da serie horaria (`/estacao/{inicio}/{fim}/{codigo}`): confirmados
  via um exemplo real de terceiro (nao documentacao oficial) para a
  estacao A728 — `DTMEDICAO`, `HRMEDICAO`, `TEMINS`, `UMDINS`, `CHUVA`,
  `VENVEL`. Nao ha exemplo para o campo de radiacao; fica de fora do
  mapeamento ate ser confirmado.

Rode uma chamada real contra as duas rotas e ajuste as constantes abaixo
antes de considerar a ingestao pronta para dados de producao.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import httpx

from app import db_enums
from app.clients.http import get_com_retry, novo_client
from app.config import get_settings

# --- Catalogo de estacoes automaticas (/estacoes/T) — TBD, sem exemplo real ---
CAMPO_CATALOGO_CODIGO = "CD_ESTACAO"
CAMPO_CATALOGO_NOME = "DC_NOME"
CAMPO_CATALOGO_LATITUDE = "VL_LATITUDE"
CAMPO_CATALOGO_LONGITUDE = "VL_LONGITUDE"
CAMPO_CATALOGO_ALTITUDE = "VL_ALTITUDE"

# --- Serie horaria (/estacao/{inicio}/{fim}/{codigo}) — confirmado via exemplo real ---
CAMPO_DATA = "DTMEDICAO"
CAMPO_HORA = "HRMEDICAO"

# Mapeamento variavel do dominio -> campo da resposta INMET + unidade gravada.
# Isolado aqui para corrigir facil apos validacao contra a API real.
CAMPOS_VARIAVEL_DIARIA: dict[str, str] = {
    db_enums.VARIAVEL_PRECIPITACAO: "CHUVA",
    db_enums.VARIAVEL_TEMPERATURA: "TEMINS",
    db_enums.VARIAVEL_UMIDADE_RELATIVA: "UMDINS",
    db_enums.VARIAVEL_VENTO: "VENVEL",
    # RADIACAO fica de fora: nenhum campo confirmado nesta fase.
}

UNIDADE_POR_VARIAVEL: dict[str, str] = {
    db_enums.VARIAVEL_PRECIPITACAO: "mm",
    db_enums.VARIAVEL_TEMPERATURA: "C",
    db_enums.VARIAVEL_UMIDADE_RELATIVA: "%",
    db_enums.VARIAVEL_VENTO: "m/s",
}


class InmetFormatoInesperadoError(RuntimeError):
    """Resposta da INMET nao tem os campos esperados.

    Sinaliza que as constantes CAMPO_* acima nao batem com a API real —
    ajustar apos rodar uma chamada de reconhecimento (ver docstring do
    modulo). Falhar alto aqui e deliberado: preferimos um erro claro a
    silenciosamente gravar dados errados.
    """


@dataclass(frozen=True)
class EstacaoInmet:
    codigo: str
    nome: str
    latitude: float
    longitude: float
    altitude: float | None


@dataclass(frozen=True)
class LeituraInmet:
    timestamp: dt.datetime
    # chave = constante VARIAVEL_* de app.db_enums
    valores: dict[str, float]


def _parse_timestamp(data_str: str, hora_str: str) -> dt.datetime:
    """Combina DTMEDICAO + HRMEDICAO num timestamp UTC.

    Formato exato de HRMEDICAO nao confirmado — aceita "HHMM", "HH:MM" ou
    hora isolada, para tolerar variacoes ate a validacao real.
    """
    data = dt.date.fromisoformat(data_str[:10])
    hora_str = hora_str.strip()
    if ":" in hora_str:
        partes = hora_str.split(":")
        hora, minuto = partes[0], partes[1]
    elif len(hora_str) >= 3:
        hora, minuto = hora_str[:-2] or "0", hora_str[-2:]
    else:
        hora, minuto = hora_str or "0", "0"
    return dt.datetime(data.year, data.month, data.day, int(hora), int(minuto), tzinfo=dt.timezone.utc)


def listar_estacoes(client: httpx.Client | None = None) -> list[EstacaoInmet]:
    settings = get_settings()
    proprio_client = client is None
    client = client or novo_client()
    try:
        resposta = get_com_retry(client, f"{settings.inmet_base_url}/estacoes/T")
        dados = resposta.json()
        estacoes: list[EstacaoInmet] = []
        for item in dados:
            try:
                altitude_bruta = item.get(CAMPO_CATALOGO_ALTITUDE)
                estacoes.append(
                    EstacaoInmet(
                        codigo=str(item[CAMPO_CATALOGO_CODIGO]),
                        nome=str(item[CAMPO_CATALOGO_NOME]),
                        latitude=float(item[CAMPO_CATALOGO_LATITUDE]),
                        longitude=float(item[CAMPO_CATALOGO_LONGITUDE]),
                        altitude=float(altitude_bruta) if altitude_bruta not in (None, "") else None,
                    )
                )
            except (KeyError, ValueError, TypeError) as exc:
                raise InmetFormatoInesperadoError(
                    "Registro do catalogo de estacoes INMET nao tem os campos esperados "
                    f"({CAMPO_CATALOGO_CODIGO}/{CAMPO_CATALOGO_NOME}/{CAMPO_CATALOGO_LATITUDE}/"
                    f"{CAMPO_CATALOGO_LONGITUDE}). Item bruto: {item!r}"
                ) from exc
        return estacoes
    finally:
        if proprio_client:
            client.close()


def serie_horaria(
    codigo: str, inicio: dt.date, fim: dt.date, client: httpx.Client | None = None
) -> list[LeituraInmet]:
    settings = get_settings()
    proprio_client = client is None
    client = client or novo_client()
    try:
        url = f"{settings.inmet_base_url}/estacao/{inicio.isoformat()}/{fim.isoformat()}/{codigo}"
        resposta = get_com_retry(client, url)
        dados = resposta.json()
        leituras: list[LeituraInmet] = []
        for item in dados:
            try:
                timestamp = _parse_timestamp(str(item[CAMPO_DATA]), str(item[CAMPO_HORA]))
            except (KeyError, ValueError, TypeError) as exc:
                raise InmetFormatoInesperadoError(
                    f"Registro da serie horaria INMET (estacao {codigo}) nao tem os campos de "
                    f"data/hora esperados ({CAMPO_DATA}/{CAMPO_HORA}). Item bruto: {item!r}"
                ) from exc

            valores: dict[str, float] = {}
            for variavel, campo in CAMPOS_VARIAVEL_DIARIA.items():
                valor_bruto = item.get(campo)
                if valor_bruto in (None, "", "null"):
                    continue  # gap real — nunca preenchido com um valor inventado
                try:
                    valores[variavel] = float(valor_bruto)
                except (TypeError, ValueError):
                    continue  # valor nao numerico: tratado como gap, nao derruba a leitura inteira
            leituras.append(LeituraInmet(timestamp=timestamp, valores=valores))
        return leituras
    finally:
        if proprio_client:
            client.close()
