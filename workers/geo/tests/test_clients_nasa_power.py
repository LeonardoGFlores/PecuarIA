"""Testes do parser do client NASA POWER, com respostas mockadas
(httpx.MockTransport). Sem chamada de rede real."""

import datetime as dt

import httpx
import pytest

from app.clients import nasa_power


def _client_mockado(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_serie_diaria_parseia_valores_e_unidades():
    corpo = {
        "properties": {
            "parameter": {
                "T2M": {"20240101": 25.5, "20240102": 26.1},
                "PRECTOTCORR": {"20240101": 0.0, "20240102": 5.2},
            }
        },
        "parameters": {
            "T2M": {"units": "C"},
            "PRECTOTCORR": {"units": "mm/day"},
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert "power.larc.nasa.gov" in str(request.url)
        return httpx.Response(200, json=corpo)

    leituras, unidades = nasa_power.serie_diaria(
        latitude=-15.78,
        longitude=-47.93,
        inicio=dt.date(2024, 1, 1),
        fim=dt.date(2024, 1, 2),
        parametros=["T2M", "PRECTOTCORR"],
        client=_client_mockado(handler),
    )

    assert unidades == {"T2M": "C", "PRECTOTCORR": "mm/day"}
    assert len(leituras) == 2
    assert leituras[0].data == dt.date(2024, 1, 1)
    assert leituras[0].valores["T2M"] == pytest.approx(25.5)
    assert leituras[1].valores["PRECTOTCORR"] == pytest.approx(5.2)


def test_serie_diaria_sentinela_ausente_vira_gap():
    corpo = {
        "properties": {"parameter": {"T2M": {"20240101": nasa_power.VALOR_AUSENTE}}},
        "parameters": {"T2M": {"units": "C"}},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=corpo)

    leituras, _ = nasa_power.serie_diaria(
        latitude=-15.78,
        longitude=-47.93,
        inicio=dt.date(2024, 1, 1),
        fim=dt.date(2024, 1, 1),
        parametros=["T2M"],
        client=_client_mockado(handler),
    )

    assert "T2M" not in leituras[0].valores


def test_serie_diaria_resposta_sem_properties_levanta_erro_claro():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"inesperado": True})

    with pytest.raises(nasa_power.NasaPowerFormatoInesperadoError):
        nasa_power.serie_diaria(
            latitude=-15.78,
            longitude=-47.93,
            inicio=dt.date(2024, 1, 1),
            fim=dt.date(2024, 1, 1),
            client=_client_mockado(handler),
        )
