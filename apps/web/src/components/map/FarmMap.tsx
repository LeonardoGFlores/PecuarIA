import type { Geometry } from "geojson";
import { LngLatBounds, Map as MapLibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import type { AreaProdutiva, Fazenda } from "../../api/types";

interface FarmMapProps {
  fazendas: Fazenda[];
  areasPorFazenda: Record<string, AreaProdutiva[]>;
}

const COR_POR_TIPO_USO: Record<string, string> = {
  pasto: "#7cb342",
  mata: "#2e7d32",
  agua: "#1976d2",
  lavoura: "#f9a825",
  infraestrutura: "#757575",
  outro: "#9e9e9e",
};

export function FarmMap({ fazendas, areasPorFazenda }: FarmMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  // "load" só ocorre uma vez no ciclo de vida do mapa; isStyleLoaded() pode
  // ficar temporariamente false apos addSource/addLayer (enquanto tiles da
  // fonte carregam), entao usamos esta ref para saber se JA passamos pelo
  // primeiro load — sem ela, um `map.once("load", ...)` registrado depois do
  // load original nunca dispara e o redesenho trava silenciosamente.
  const carregadoRef = useRef(false);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new MapLibreMap({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {},
        layers: [{ id: "background", type: "background", paint: { "background-color": "#eef2eb" } }],
      },
      center: [-47.93, -15.78],
      zoom: 4,
      canvasContextAttributes: { preserveDrawingBuffer: true },
    });
    map.once("load", () => {
      carregadoRef.current = true;
    });
    mapRef.current = map;

    return () => {
      carregadoRef.current = false;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const drawLayers = () => {
      for (const layer of map.getStyle()?.layers ?? []) {
        if (layer.id.startsWith("fazenda-") || layer.id.startsWith("area-")) {
          map.removeLayer(layer.id);
        }
      }
      for (const sourceId of Object.keys(map.getStyle()?.sources ?? {})) {
        if (sourceId.startsWith("fazenda-") || sourceId.startsWith("area-")) {
          map.removeSource(sourceId);
        }
      }

      const bounds = new LngLatBounds();
      let hasBounds = false;

      for (const fazenda of fazendas) {
        const sourceId = `fazenda-${fazenda.id}`;
        map.addSource(sourceId, { type: "geojson", data: fazenda.geom as Geometry });
        map.addLayer({
          id: `fazenda-${fazenda.id}-outline`,
          type: "line",
          source: sourceId,
          paint: { "line-color": "#3e2723", "line-width": 2 },
        });

        for (const area of areasPorFazenda[fazenda.id] ?? []) {
          const areaSourceId = `area-${area.id}`;
          map.addSource(areaSourceId, { type: "geojson", data: area.geom as Geometry });
          map.addLayer({
            id: `area-${area.id}-fill`,
            type: "fill",
            source: areaSourceId,
            paint: {
              "fill-color": COR_POR_TIPO_USO[area.tipo_uso] ?? "#9e9e9e",
              "fill-opacity": 0.5,
            },
          });
        }

        if (fazenda.geom.type === "Polygon") {
          for (const ring of fazenda.geom.coordinates) {
            for (const [lng, lat] of ring) {
              bounds.extend([lng, lat]);
              hasBounds = true;
            }
          }
        }
      }

      if (hasBounds) {
        map.fitBounds(bounds, { padding: 40, maxZoom: 15 });
      }
    };

    if (carregadoRef.current || map.isStyleLoaded()) {
      drawLayers();
    } else {
      map.once("load", drawLayers);
    }
  }, [fazendas, areasPorFazenda]);

  return <div ref={containerRef} style={{ width: "100%", height: "100%" }} />;
}
