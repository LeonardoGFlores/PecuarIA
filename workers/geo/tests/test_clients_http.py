"""Testes de post_com_retry (usado pela busca STAC) com httpx.MockTransport
— sem rede real. time.sleep mockado para o teste nao esperar o backoff de
verdade."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from app.clients.http import post_com_retry


def _client_mockado(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def sem_sleep_de_verdade():
    with patch("app.clients.http.time.sleep"):
        yield


def test_post_com_retry_sucesso_na_primeira_tentativa():
    chamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(request)
        return httpx.Response(200, json={"ok": True})

    resposta = post_com_retry(_client_mockado(handler), "https://exemplo.test/search", json={"a": 1})

    assert resposta.json() == {"ok": True}
    assert len(chamadas) == 1


def test_post_com_retry_tenta_novamente_em_503_e_depois_sucede():
    respostas = [httpx.Response(503), httpx.Response(200, json={"ok": True})]

    def handler(request: httpx.Request) -> httpx.Response:
        return respostas.pop(0)

    resposta = post_com_retry(_client_mockado(handler), "https://exemplo.test/search", json={})

    assert resposta.json() == {"ok": True}


def test_post_com_retry_esgota_tentativas_e_propaga_erro():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    with pytest.raises(httpx.HTTPStatusError):
        post_com_retry(_client_mockado(handler), "https://exemplo.test/search", json={}, max_tentativas=2)


def test_post_com_retry_nao_tenta_novamente_em_erro_4xx_nao_retryable():
    chamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(request)
        return httpx.Response(400)

    with pytest.raises(httpx.HTTPStatusError):
        post_com_retry(_client_mockado(handler), "https://exemplo.test/search", json={})

    assert len(chamadas) == 1


def test_post_com_retry_tenta_novamente_em_falha_de_transporte():
    tentativas = {"contador": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        tentativas["contador"] += 1
        if tentativas["contador"] < 2:
            raise httpx.ConnectError("conexao recusada", request=request)
        return httpx.Response(200, json={"ok": True})

    resposta = post_com_retry(_client_mockado(handler), "https://exemplo.test/search", json={})

    assert resposta.json() == {"ok": True}
