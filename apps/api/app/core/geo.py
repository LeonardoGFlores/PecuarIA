from typing import Any

from fastapi import HTTPException
from geoalchemy2 import WKBElement
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import mapping, shape
from shapely.validation import explain_validity


def geojson_to_geom(geojson: dict[str, Any], srid: int = 4326) -> WKBElement:
    """Converte um dict GeoJSON validado em uma geometria pronta para persistir.

    Rejeita geometrias topologicamente invalidas (self-intersection, anel nao
    fechado corretamente etc.) — o criterio de aceite da Fase 1 e "geometrias
    validas", nao apenas GeoJSON bem formado.
    """
    geom = shape(geojson)
    if not geom.is_valid:
        raise HTTPException(status_code=422, detail=f"Geometria invalida: {explain_validity(geom)}")
    return from_shape(geom, srid=srid)


def geom_to_geojson(geom: WKBElement) -> dict[str, Any]:
    return mapping(to_shape(geom))
