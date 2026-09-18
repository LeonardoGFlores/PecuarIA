"""Resolucao de escala/offset do produto Sentinel-2 L2A por asset do item
STAC (docs/specs/02, passo 4) — aplicada as bandas espectrais ANTES de
qualquer calculo de indice. Puro: opera sobre o JSON do item STAC, sem rede
nem raster.

Confianca media-alta, baseada em documentacao publica, NAO confirmada com
chamada real ao Earth Search (mesma ressalva do INMET na Fase 2 — ver
riscos documentados no README/plano da Fase 3).
"""

from __future__ import annotations

# Fallback quando o item STAC nao traz a extensao raster:bands no asset.
ESCALA_PADRAO_FALLBACK = 1.0 / 10000
OFFSET_PADRAO_BASELINE_ANTIGA = 0.0
OFFSET_PADRAO_BASELINE_NOVA = -0.1  # BOA_ADD_OFFSET=-1000, ESA 2022-01-25

BASELINE_MINIMA_COM_OFFSET = "04.00"


def resolver_escala_offset(asset: dict, propriedades_item: dict) -> tuple[float, float]:
    """Retorna `(scale, offset)` para um asset (banda) do item STAC.

    Preferencia: extensao `raster:bands` do proprio asset
    (`asset["raster:bands"][0]["scale"|"offset"]`). Se ausente, usa o
    fallback por baseline de processamento
    (`propriedades_item["s2:processing_baseline"]`) — baseline ausente e
    tratado como anterior a "04.00" (offset=0), a opcao mais conservadora.
    """
    bandas_raster = asset.get("raster:bands")
    if bandas_raster:
        banda = bandas_raster[0]
        if "scale" in banda and "offset" in banda:
            return float(banda["scale"]), float(banda["offset"])

    baseline = propriedades_item.get("s2:processing_baseline")
    offset = (
        OFFSET_PADRAO_BASELINE_NOVA
        if _baseline_aplica_offset(baseline)
        else OFFSET_PADRAO_BASELINE_ANTIGA
    )
    return ESCALA_PADRAO_FALLBACK, offset


def _baseline_aplica_offset(baseline: str | None) -> bool:
    if not baseline:
        return False
    try:
        return _versao_baseline(baseline) >= _versao_baseline(BASELINE_MINIMA_COM_OFFSET)
    except ValueError:
        return False


def _versao_baseline(baseline: str) -> tuple[int, ...]:
    return tuple(int(parte) for parte in baseline.split("."))
