"""Testes dos parsers do client INMET, com respostas mockadas (httpx.MockTransport).

Sem chamada de rede real — ver ressalva de nomes de campo nao confirmados no
docstring de app/clients/inmet.py.
"""

import datetime as dt

import httpx
import pytest

from app import db_enums
from app.clients import inmet


def _client_mockado(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_listar_estacoes_parseia_catalogo_valido():
    corpo = [
        {
            inmet.CAMPO_CATALOGO_CODIGO: "A728",
            inmet.CAMPO_CATALOGO_NOME: "BRASILIA",
            inmet.CAMPO_CATALOGO_LATITUDE: "-15.789",
            inmet.CAMPO_CATALOGO_LONGITUDE: "-47.925",
            inmet.CAMPO_CATALOGO_ALTITUDE: "1160.96",
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/estacoes/T"
        return httpx.Response(200, json=corpo)

    estacoes = inmet.listar_estacoes(client=_client_mockado(handler))

    assert len(estacoes) == 1
    assert estacoes[0].codigo == "A728"
    assert estacoes[0].nome == "BRASILIA"
    assert estacoes[0].latitude == pytest.approx(-15.789)
    assert estacoes[0].altitude == pytest.approx(1160.96)


def test_listar_estacoes_sem_altitude_vira_none():
    corpo = [
        {
            inmet.CAMPO_CATALOGO_CODIGO: "A728",
            inmet.CAMPO_CATALOGO_NOME: "BRASILIA",
            inmet.CAMPO_CATALOGO_LATITUDE: "-15.789",
            inmet.CAMPO_CATALOGO_LONGITUDE: "-47.925",
            inmet.CAMPO_CATALOGO_ALTITUDE: None,
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=corpo)

    estacoes = inmet.listar_estacoes(client=_client_mockado(handler))
    assert estacoes[0].altitude is None


def test_listar_estacoes_campo_faltante_levanta_erro_claro():
    corpo = [{"campo_desconhecido": "valor"}]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=corpo)

    with pytest.raises(inmet.InmetFormatoInesperadoError):
        inmet.listar_estacoes(client=_client_mockado(handler))


def test_serie_horaria_parseia_leitura_valida_e_combina_timestamp():
    corpo = [
        {
            inmet.CAMPO_DATA: "2024-01-01",
            inmet.CAMPO_HORA: "1200",
            "CHUVA": "5.4",
            "TEMINS": "27.3",
            "UMDINS": "68",
            "VENVEL": "2.1",
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/estacao/2024-01-01/2024-01-02/A728"
        return httpx.Response(200, json=corpo)

    leituras = inmet.serie_horaria(
        "A728", dt.date(2024, 1, 1), dt.date(2024, 1, 2), client=_client_mockado(handler)
    )

    assert len(leituras) == 1
    leitura = leituras[0]
    assert leitura.timestamp == dt.datetime(2024, 1, 1, 12, 0, tzinfo=dt.timezone.utc)
    assert leitura.valores[db_enums.VARIAVEL_PRECIPITACAO] == pytest.approx(5.4)
    assert leitura.valores[db_enums.VARIAVEL_TEMPERATURA] == pytest.approx(27.3)
    assert leitura.valores[db_enums.VARIAVEL_UMIDADE_RELATIVA] == pytest.approx(68)
    assert leitura.valores[db_enums.VARIAVEL_VENTO] == pytest.approx(2.1)


def test_serie_horaria_campo_nulo_vira_gap_nao_erro():
    corpo = [
        {
            inmet.CAMPO_DATA: "2024-01-01",
            inmet.CAMPO_HORA: "0000",
            "CHUVA": None,
            "TEMINS": "27.3",
            "UMDINS": None,
            "VENVEL": "",
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=corpo)

    leituras = inmet.serie_horaria(
        "A728", dt.date(2024, 1, 1), dt.date(2024, 1, 2), client=_client_mockado(handler)
    )

    valores = leituras[0].valores
    assert db_enums.VARIAVEL_PRECIPITACAO not in valores
    assert db_enums.VARIAVEL_UMIDADE_RELATIVA not in valores
    assert db_enums.VARIAVEL_VENTO not in valores
    assert valores[db_enums.VARIAVEL_TEMPERATURA] == pytest.approx(27.3)


def test_serie_horaria_sem_data_ou_hora_levanta_erro_claro():
    corpo = [{"CHUVA": "1.0"}]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=corpo)

    with pytest.raises(inmet.InmetFormatoInesperadoError):
        inmet.serie_horaria("A728", dt.date(2024, 1, 1), dt.date(2024, 1, 2), client=_client_mockado(handler))


@pytest.mark.parametrize(
    ("hora_str", "esperado"),
    [
        ("0000", dt.time(0, 0)),
        ("1230", dt.time(12, 30)),
        ("12:30", dt.time(12, 30)),
        ("0", dt.time(0, 0)),
    ],
)
def test_parse_timestamp_tolera_formatos_de_hora(hora_str, esperado):
    timestamp = inmet._parse_timestamp("2024-01-01", hora_str)
    assert timestamp.time() == esperado
    assert timestamp.tzinfo == dt.timezone.utc
