from app.processing.escala import (
    ESCALA_PADRAO_FALLBACK,
    OFFSET_PADRAO_BASELINE_ANTIGA,
    OFFSET_PADRAO_BASELINE_NOVA,
    resolver_escala_offset,
)


def test_usa_raster_bands_do_asset_quando_presente():
    asset = {"raster:bands": [{"scale": 0.0001, "offset": -0.1}]}
    scale, offset = resolver_escala_offset(asset, propriedades_item={})
    assert scale == 0.0001
    assert offset == -0.1


def test_fallback_baseline_nova_usa_offset_negativo():
    asset = {}
    scale, offset = resolver_escala_offset(asset, propriedades_item={"s2:processing_baseline": "05.00"})
    assert scale == ESCALA_PADRAO_FALLBACK
    assert offset == OFFSET_PADRAO_BASELINE_NOVA


def test_fallback_baseline_exatamente_no_limite_usa_offset_negativo():
    asset = {}
    scale, offset = resolver_escala_offset(asset, propriedades_item={"s2:processing_baseline": "04.00"})
    assert offset == OFFSET_PADRAO_BASELINE_NOVA


def test_fallback_baseline_antiga_usa_offset_zero():
    asset = {}
    scale, offset = resolver_escala_offset(asset, propriedades_item={"s2:processing_baseline": "03.01"})
    assert scale == ESCALA_PADRAO_FALLBACK
    assert offset == OFFSET_PADRAO_BASELINE_ANTIGA


def test_fallback_sem_baseline_assume_conservador_offset_zero():
    asset = {}
    scale, offset = resolver_escala_offset(asset, propriedades_item={})
    assert scale == ESCALA_PADRAO_FALLBACK
    assert offset == OFFSET_PADRAO_BASELINE_ANTIGA


def test_fallback_baseline_com_formato_inesperado_nao_quebra():
    asset = {}
    scale, offset = resolver_escala_offset(asset, propriedades_item={"s2:processing_baseline": "N/A"})
    assert scale == ESCALA_PADRAO_FALLBACK
    assert offset == OFFSET_PADRAO_BASELINE_ANTIGA


def test_raster_bands_presente_mas_sem_scale_offset_cai_no_fallback():
    asset = {"raster:bands": [{"nodata": 0}]}
    scale, offset = resolver_escala_offset(asset, propriedades_item={"s2:processing_baseline": "05.00"})
    assert scale == ESCALA_PADRAO_FALLBACK
    assert offset == OFFSET_PADRAO_BASELINE_NOVA
