"""Testes do client STAC com httpx.MockTransport e JSON STAC sintetico —
sem rede real (earth-search.aws.element84.com esta bloqueado nesta
sandbox). Cobre parsing de item/assets, filtro de nuvem via query, asset
ausente, e paginacao via links rel=next.
"""

from __future__ import annotations

import datetime as dt
import json

import httpx
import pytest

from app.clients.stac import AssetAusenteError, buscar_cenas

GEOMETRIA_FAZENDA = {"type": "Polygon", "coordinates": [[[-47, -15], [-47, -14.99], [-46.99, -14.99], [-46.99, -15], [-47, -15]]]}


def _item_stac(item_id: str, nuvem_pct: float = 5.0, sem_asset: str | None = None) -> dict:
    assets = {
        "red": {"href": f"https://s3.example/{item_id}/B04.tif", "raster:bands": [{"scale": 0.0001, "offset": -0.1}]},
        "nir": {"href": f"https://s3.example/{item_id}/B08.tif", "raster:bands": [{"scale": 0.0001, "offset": -0.1}]},
        "blue": {"href": f"https://s3.example/{item_id}/B02.tif", "raster:bands": [{"scale": 0.0001, "offset": -0.1}]},
        "scl": {"href": f"https://s3.example/{item_id}/SCL.tif"},
    }
    if sem_asset:
        assets.pop(sem_asset)
    return {
        "id": item_id,
        "geometry": GEOMETRIA_FAZENDA,
        "properties": {
            "datetime": "2024-06-15T13:30:00Z",
            "eo:cloud_cover": nuvem_pct,
            "s2:processing_baseline": "05.00",
        },
        "assets": assets,
    }


def _client_mockado(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_buscar_cenas_parseia_itens_e_assets():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        corpo = json.loads(request.content)
        assert corpo["query"]["eo:cloud_cover"]["lte"] == 90.0
        return httpx.Response(200, json={"features": [_item_stac("cena-1")], "links": []})

    itens = buscar_cenas(
        GEOMETRIA_FAZENDA,
        dt.date(2024, 6, 1),
        dt.date(2024, 6, 30),
        cobertura_nuvem_maxima_pct=90.0,
        client=_client_mockado(handler),
    )

    assert len(itens) == 1
    item = itens[0]
    assert item.id == "cena-1"
    assert item.cobertura_nuvem_pct == 5.0
    assert set(item.ativos.keys()) == {"red", "nir", "blue", "scl"}
    assert item.ativos["red"]["href"].endswith("B04.tif")
    assert item.propriedades["s2:processing_baseline"] == "05.00"


def test_buscar_cenas_asset_ausente_levanta_erro_claro():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"features": [_item_stac("cena-sem-scl", sem_asset="scl")], "links": []})

    with pytest.raises(AssetAusenteError, match="scl"):
        buscar_cenas(
            GEOMETRIA_FAZENDA,
            dt.date(2024, 6, 1),
            dt.date(2024, 6, 30),
            cobertura_nuvem_maxima_pct=90.0,
            client=_client_mockado(handler),
        )


def test_buscar_cenas_segue_paginacao_via_links_next():
    paginas = [
        {
            "features": [_item_stac("cena-pagina-1")],
            "links": [{"rel": "next", "href": "https://stac.example/search?page=2", "body": {"page": 2}}],
        },
        {"features": [_item_stac("cena-pagina-2")], "links": []},
    ]
    urls_chamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls_chamadas.append(str(request.url))
        return httpx.Response(200, json=paginas.pop(0))

    itens = buscar_cenas(
        GEOMETRIA_FAZENDA,
        dt.date(2024, 6, 1),
        dt.date(2024, 6, 30),
        cobertura_nuvem_maxima_pct=90.0,
        client=_client_mockado(handler),
    )

    assert [item.id for item in itens] == ["cena-pagina-1", "cena-pagina-2"]
    assert urls_chamadas[1] == "https://stac.example/search?page=2"


def test_buscar_cenas_sem_resultados_retorna_lista_vazia():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"features": [], "links": []})

    itens = buscar_cenas(
        GEOMETRIA_FAZENDA,
        dt.date(2024, 6, 1),
        dt.date(2024, 6, 30),
        cobertura_nuvem_maxima_pct=90.0,
        client=_client_mockado(handler),
    )

    assert itens == []
