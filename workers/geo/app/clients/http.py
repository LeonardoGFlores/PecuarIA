"""Factory de cliente HTTP com timeout e retry/backoff exponencial.

Usado por `clients/inmet.py` e `clients/nasa_power.py`. O rate limit real da
INMET nao e documentado — o backoff aqui e postura defensiva, nao um numero
confirmado seguro (ver docs/specs da Fase 2, secao "Riscos").
"""

from __future__ import annotations

import logging
import time

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def novo_client() -> httpx.Client:
    settings = get_settings()
    return httpx.Client(timeout=settings.http_timeout_segundos)


def get_com_retry(
    client: httpx.Client,
    url: str,
    params: dict[str, str] | None = None,
    max_tentativas: int = 3,
) -> httpx.Response:
    """GET com backoff exponencial em 429/5xx e erros de transporte.

    Nao tenta novamente em 4xx que nao seja 429 (erro do cliente, repetir nao
    ajuda). Lanca a ultima excecao/erro apos esgotar as tentativas.
    """
    atraso_segundos = 1.0
    ultima_excecao: Exception | None = None

    for tentativa in range(max_tentativas + 1):
        try:
            resposta = client.get(url, params=params)
        except httpx.TransportError as exc:
            ultima_excecao = exc
            if tentativa < max_tentativas:
                logger.warning("Falha de transporte ao chamar %s (tentativa %d): %s", url, tentativa + 1, exc)
                time.sleep(atraso_segundos)
                atraso_segundos *= 2
                continue
            raise

        if resposta.status_code in _RETRYABLE_STATUS and tentativa < max_tentativas:
            logger.warning(
                "HTTP %d ao chamar %s (tentativa %d) — nova tentativa em %.0fs",
                resposta.status_code,
                url,
                tentativa + 1,
                atraso_segundos,
            )
            time.sleep(atraso_segundos)
            atraso_segundos *= 2
            continue

        resposta.raise_for_status()
        return resposta

    assert ultima_excecao is not None
    raise ultima_excecao


def post_com_retry(
    client: httpx.Client,
    url: str,
    json: dict,
    max_tentativas: int = 3,
) -> httpx.Response:
    """POST com o mesmo backoff exponencial de `get_com_retry` — usado pela
    busca STAC (`POST /search`). Rate limit do Earth Search nao e
    documentado; postura defensiva igual a INMET/NASA POWER, sem numero
    confirmado seguro."""
    atraso_segundos = 1.0
    ultima_excecao: Exception | None = None

    for tentativa in range(max_tentativas + 1):
        try:
            resposta = client.post(url, json=json)
        except httpx.TransportError as exc:
            ultima_excecao = exc
            if tentativa < max_tentativas:
                logger.warning("Falha de transporte ao chamar %s (tentativa %d): %s", url, tentativa + 1, exc)
                time.sleep(atraso_segundos)
                atraso_segundos *= 2
                continue
            raise

        if resposta.status_code in _RETRYABLE_STATUS and tentativa < max_tentativas:
            logger.warning(
                "HTTP %d ao chamar %s (tentativa %d) — nova tentativa em %.0fs",
                resposta.status_code,
                url,
                tentativa + 1,
                atraso_segundos,
            )
            time.sleep(atraso_segundos)
            atraso_segundos *= 2
            continue

        resposta.raise_for_status()
        return resposta

    assert ultima_excecao is not None
    raise ultima_excecao
