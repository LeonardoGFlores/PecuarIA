"""Client STAC (SpatioTemporal Asset Catalog) para o Earth Search da
Element84 — fonte escolhida para Sentinel-2 L2A (docs/specs/02): sem
autenticacao, ao contrario de Planetary Computer (SAS token) e Copernicus
Data Space (OAuth2), STAC padrao, assets em COG publico no S3.

Nomes de asset (`red`, `nir`, `blue`, `scl`) e o formato de `raster:bands`/
`s2:processing_baseline` sao baseados em documentacao publica, NAO
confirmados com chamada real — o proxy de rede desta sessao bloqueia
earth-search.aws.element84.com (mesma ressalva do INMET na Fase 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import httpx

from app.clients.http import post_com_retry
from app.config import get_settings

# Nomes de asset assumidos do Earth Search para Sentinel-2 L2A. Se um item
# nao trouxer um destes, falha com erro claro — nunca substitui
# silenciosamente por outro asset (docs/specs/02, riscos assumidos).
ASSETS_NECESSARIOS = ("red", "nir", "blue", "scl")


class AssetAusenteError(RuntimeError):
    """Um item STAC nao traz um dos assets exigidos pelo pipeline."""


@dataclass(frozen=True)
class ItemSTAC:
    id: str
    data_aquisicao: str
    cobertura_nuvem_pct: float
    geometria: dict
    ativos: dict[str, dict]
    propriedades: dict


def _extrair_link_next(pagina: dict) -> dict | None:
    for link in pagina.get("links", []):
        if link.get("rel") == "next":
            return link
    return None


def _parsear_item(item_json: dict) -> ItemSTAC:
    propriedades = item_json.get("properties", {})
    ativos_brutos = item_json.get("assets", {})

    ativos: dict[str, dict] = {}
    for nome in ASSETS_NECESSARIOS:
        asset = ativos_brutos.get(nome)
        if asset is None:
            raise AssetAusenteError(
                f"asset '{nome}' nao encontrado no item STAC '{item_json.get('id')}'"
            )
        ativos[nome] = asset

    return ItemSTAC(
        id=item_json["id"],
        data_aquisicao=propriedades["datetime"],
        cobertura_nuvem_pct=float(propriedades.get("eo:cloud_cover", 0.0)),
        geometria=item_json["geometry"],
        ativos=ativos,
        propriedades=propriedades,
    )


def buscar_cenas(
    geometria_geojson: dict,
    data_inicio: date,
    data_fim: date,
    cobertura_nuvem_maxima_pct: float,
    client: httpx.Client | None = None,
) -> list[ItemSTAC]:
    """Busca itens Sentinel-2 L2A que intersectam `geometria_geojson` no
    intervalo [data_inicio, data_fim], filtrando por `eo:cloud_cover` no
    proprio STAC (sem tocar raster — economiza processamento antes do
    download). Segue paginacao via `links` (rel=next) genericamente, nunca
    hardcoda offset/token."""
    settings = get_settings()
    client_proprio = client or httpx.Client(timeout=settings.http_timeout_segundos)

    url = f"{settings.sentinel2_stac_base_url}/search"
    corpo = {
        "collections": [settings.sentinel2_colecao],
        "intersects": geometria_geojson,
        "datetime": f"{data_inicio.isoformat()}T00:00:00Z/{data_fim.isoformat()}T23:59:59Z",
        "query": {"eo:cloud_cover": {"lte": cobertura_nuvem_maxima_pct}},
        "limit": 100,
    }

    itens: list[ItemSTAC] = []
    while True:
        resposta = post_com_retry(client_proprio, url, json=corpo)
        pagina = resposta.json()

        for item_json in pagina.get("features", []):
            itens.append(_parsear_item(item_json))

        link_next = _extrair_link_next(pagina)
        if link_next is None:
            break
        url = link_next["href"]
        corpo = link_next.get("body", corpo)

    return itens
