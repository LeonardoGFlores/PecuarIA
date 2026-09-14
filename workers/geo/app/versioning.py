"""Versoes de pipeline gravadas no manifesto de execucao (docs/specs/00) e em
`observacao_meteorologica.versao_processamento` / `avaliacao_representatividade.
versao_algoritmo`. Bump manual aqui quando a logica de parsing, mapeamento de
campos ou o algoritmo de qualidade mudar — e o unico lugar a editar.
"""

VERSAO_INGESTAO_INMET = "inmet-v1"
VERSAO_INGESTAO_NASA_POWER = "nasa-power-v1"
VERSAO_QUALIDADE_REPRESENTATIVIDADE = "representatividade-v1"
VERSAO_DESCOBERTA_SENTINEL2 = "descoberta-sentinel2-v1"
VERSAO_PROCESSAMENTO_NDVI_EVI = "ndvi-evi-v1"
VERSAO_ANALISE_TENDENCIA_VEGETACAO = "tendencia-vegetacao-v1"
