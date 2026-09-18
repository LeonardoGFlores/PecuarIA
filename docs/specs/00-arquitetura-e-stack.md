# 00 — Arquitetura e stack

## Contexto

A especificação de produto da PecuarIA define 9 componentes funcionais (cadastro territorial,
catálogo de fontes, ingestão, qualidade, processamento geoespacial, análise temporal,
diagnóstico, cenários, apresentação) sobre uma arquitetura já decidida: aplicação web + API +
PostgreSQL/PostGIS + armazenamento de arquivos, com um worker de processamento geoespacial
separado da API por fila de tarefas. Este documento não reabre essa decisão — ele escolhe a
stack concreta dentro dela, para que toda implementação futura (Fases 2–9 do roadmap) parta da
mesma base.

## Requisitos

### P0 — sem isso não serve
- Um único componente de processamento geoespacial/série temporal, separado da API por fila de
  tarefas (não acoplado ao ciclo de request/response da API).
- Banco relacional com suporte nativo a geometria (PostGIS) — geometrias de propriedade,
  áreas produtivas e estações não podem virar campos de texto ou JSON sem índice espacial.
- Armazenamento de objetos para rasters (cenas Sentinel-2 recortadas, GeoTIFFs de índices) —
  rasters não pertencem ao banco relacional.
- Todo processamento (NDVI/EVI, diagnóstico, cenário) precisa produzir um manifesto de execução
  rastreável: quais fontes, quais versões, quais parâmetros geraram aquele resultado.

### P1 — importante, mas não bloqueia
- Linguagem única (Python) em API e worker, para reaproveitar validação de geometria e modelos
  de dados sem duplicar regras em duas linguagens.
- Ambiente local reproduzível via Docker Compose (banco, fila, storage) sem dependência de
  serviços cloud para desenvolver.

### P2 — bom ter
- Observabilidade básica (logs estruturados) desde o início, para que falhas de ingestão
  (Fase 2) e processamento (Fase 3) sejam diagnosticáveis sem instrumentação retroativa.

## Mapeamento componente → stack

| Componente (spec de produto) | Escolha concreta | Por quê |
|---|---|---|
| Cadastro territorial | API em FastAPI (Python) | Tipagem via Pydantic serve diretamente como contrato de dados (doc 01); assíncrono nativo. |
| Catálogo de fontes | Tabelas PostgreSQL, expostas por rotas da mesma API | Não é um serviço separado nesta fase — é cadastro relacional comum. |
| Ingestão | Tasks Celery agendadas (Celery beat) por tipo de fonte | Cada fonte (INMET, NASA POWER, Sentinel-2, cotações) tem sua própria task e calendário; isolar da API evita que uma ingestão lenta bloqueie requisições. |
| Qualidade | Camada de validação em `workers/geo/app/quality/` e regras Pydantic na API | Ver critérios de completude/atualização/consistência do doc 01. |
| Processamento geoespacial | Worker Python (`workers/geo`): rasterio, rioxarray, shapely, geopandas, numpy | Ecossistema padrão para raster + vetor; evita reimplementar manipulação de GeoTIFF. |
| Análise temporal | Módulo Python no worker (pandas) consumido pela API para séries/tendência | Mesmo processo que já lê as séries brutas; evita duplicar leitura de dados. |
| Diagnóstico | Camada de serviço na API (`apps/api/app/diagnostics/`), regras declarativas — não é um modelo de ML | Ver doc 03: o motor cruza evidências com regras explícitas, não infere causas por aprendizado estatístico. |
| Cenários | Camada de serviço na API (`apps/api/app/scenarios/`) | Mesma razão do diagnóstico: restrições e simulação são regras de negócio auditáveis, não caixa-preta. |
| Apresentação | Web app Vite + React + TypeScript, mapas com MapLibre GL | MapLibre é open-source e não exige chave de API paga para renderizar geometrias/rasters próprios. |

## Stack por camada

| Camada | Escolha | Versão mínima |
|---|---|---|
| Banco de dados | PostgreSQL + extensão PostGIS | Postgres 15, PostGIS 3.4 |
| ORM / migrations | SQLAlchemy 2.x + GeoAlchemy2; Alembic | — |
| API | FastAPI + Pydantic v2 + Uvicorn | Python 3.11+ |
| Fila de tarefas | Redis (broker) + Celery | Redis 7 |
| Processamento geoespacial | rasterio, rioxarray, shapely, geopandas, numpy, pandas | — |
| Armazenamento de objetos | S3-compatible: MinIO (local/self-host), S3 ou Cloudflare R2 (produção) | — |
| Web app | Vite + React 18 + TypeScript; MapLibre GL JS | Node 20+ |
| Orquestração local | Docker Compose | — |

## Manifesto de execução

Toda execução de processamento (ingestão, cálculo de índice, diagnóstico, simulação de
cenário) grava um registro em `execucao_processamento` com, no mínimo:
- `id`, `tipo` (ingestao_clima / indice_vegetacao / diagnostico / cenario / etc.)
- `entrada_fontes` — lista de IDs de fonte + suas versões usadas como entrada
- `parametros` — parâmetros do processamento (ex.: limiar de cobertura válida, janela de
  comparação sazonal)
- `versao_pipeline` — versão do código/algoritmo que gerou o resultado
- `iniciado_em`, `concluido_em`, `status` (sucesso/falha/parcial)
- `saida_referencias` — IDs/paths dos registros ou objetos produzidos

Esse manifesto é o que permite, na tela de Diagnóstico e no Relatório (telas prioritárias 3 e
8), o usuário clicar em uma conclusão e ver exatamente quais dados e qual versão de
processamento a sustentam.

## Lacunas identificadas

Como o repositório partiu vazio, não há lacunas de código herdadas — mas ficam registradas
aqui decisões que este documento deliberadamente não fecha, para não bloquear o scaffold:
- Escolha final de provedor de storage em produção (MinIO self-host vs. S3 vs. R2) — o contrato
  (S3-compatible) é fixado agora; o provedor pode mudar sem alterar código.
- Autenticação/autorização de usuários (multi-fazenda, múltiplos produtores) não está definida
  nesta fase — a Fase 1 assume um único usuário/contexto operando sobre suas próprias fazendas.

## Fora de escopo

- Escolha de provedor cloud definitivo para produção.
- Autenticação, multi-tenant e controle de acesso granular.
- CI/CD e pipeline de deploy — este documento cobre apenas a stack de desenvolvimento/execução.
