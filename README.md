# PecuarIA

Painéis de controle

Plataforma de avaliação de fazendas: o que a fazenda pode produzir e o que está
limitando a operação atual, a partir de território, meteorologia, vegetação
(NDVI/EVI), perfil operacional e oferta regional. A especificação completa do
produto e a arquitetura estão em [`docs/specs/`](docs/specs/):

- [`00-arquitetura-e-stack.md`](docs/specs/00-arquitetura-e-stack.md) — componentes e stack.
- [`01-contrato-dados-fontes.md`](docs/specs/01-contrato-dados-fontes.md) — modelo de dados das 5 camadas de evidência.
- [`02-processamento-ndvi-evi.md`](docs/specs/02-processamento-ndvi-evi.md) — pipeline Sentinel-2 L2A.
- [`03-motor-diagnostico-gargalos.md`](docs/specs/03-motor-diagnostico-gargalos.md) — regras do motor de diagnóstico (Fase 6).
- [`04-analise-temporal.md`](docs/specs/04-analise-temporal.md) — tendência, comparação sazonal e detecção de lacunas.

Este repositório cobriu as Fases 1 a 4 do roadmap: cadastro territorial,
catálogo de fontes, integração meteorológica (INMET + NASA POWER como
fallback em grade, com avaliação de representatividade por variável),
processamento de vegetação (NDVI/EVI via Sentinel-2 L2A) e análise temporal
(tendência/sazonalidade de vegetação + detecção de lacunas nas duas
séries). As demais fases (perfil do produtor/oferta regional, diagnóstico,
cenários) ainda não têm código além do schema — ver a spec que as guia.

**Nomes de campo da API do INMET não confirmados**: o ambiente onde a Fase 2
foi implementada bloqueia acesso de rede a `apitempo.inmet.gov.br` e
`power.larc.nasa.gov` — os clients foram escritos com base em pesquisa e um
exemplo de terceiro, não em chamadas reais. Antes de rodar a ingestão INMET
contra dados de produção, valide `workers/geo/app/clients/inmet.py`
(constantes `CAMPO_CATALOGO_*` e `CAMPOS_VARIAVEL_DIARIA`) com uma chamada
real e ajuste se necessário.

**Nomes de asset e metadados do STAC (Fase 3) não confirmados**: o mesmo
ambiente bloqueia acesso a `earth-search.aws.element84.com`. Os nomes de
asset assumidos (`red`, `nir`, `blue`, `scl`, em
`workers/geo/app/clients/stac.py`) e o fallback de escala/offset por
baseline de processamento (`workers/geo/app/processing/escala.py`) vêm de
documentação pública, não de uma chamada real — se algum nome de asset
divergir, a descoberta falha com um erro claro (nunca substitui por outro
asset silenciosamente). Valide contra uma chamada real antes de produção.

## Estrutura

```
apps/
  api/      # FastAPI: territorio, catalogo de fontes, endpoints de meteorologia, Alembic
  web/      # Vite + React + TypeScript + MapLibre GL
workers/
  geo/      # Celery: ingestao INMET/NASA POWER, avaliacao de representatividade
infra/
  docker-compose.yml   # Postgres+PostGIS, Redis, MinIO para dev local
docs/
  specs/    # Especificações de produto e técnicas
```

## Rodando localmente

Pré-requisitos: Docker, Python 3.11+, Node 20+.

### 1. Infraestrutura (Postgres+PostGIS, Redis, MinIO)

```bash
cd infra
cp .env.example .env
docker compose --env-file .env up -d
```

### 2. API

```bash
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export DATABASE_URL="postgresql+psycopg://pecuaria:pecuaria@localhost:5432/pecuaria"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

A API sobe em `http://localhost:8000` (docs interativas em `/docs`).

### 3. Worker geoespacial

```bash
cd workers/geo
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export DATABASE_URL="postgresql+psycopg://pecuaria:pecuaria@localhost:5432/pecuaria"
export CELERY_BROKER_URL="redis://localhost:6379/0"
export CELERY_RESULT_BACKEND="redis://localhost:6379/1"
celery -A app.tasks worker --loglevel=info
```

Para a ingestão rodar nos horários agendados (ver tabela abaixo), sobe
também o beat, num terminal separado:

```bash
celery -A app.tasks beat --loglevel=info
```

Tasks disponíveis nesta fase:

| Task | Agenda (beat) | O que faz |
|---|---|---|
| `clima.inmet.sincronizar_catalogo` | mensal (dia 1, 03h) | Upsert do catálogo de estações automáticas do INMET. |
| `clima.inmet.despachar_incrementais` | diário (06h) | Decide backfill/incremental por estação e enfileira `ingerir_observacoes`. |
| `clima.inmet.ingerir_observacoes` | sob demanda | Busca e grava a série horária de uma estação numa janela. |
| `clima.nasa_power.despachar_refresh` | semanal (segunda, 05h) | Refresh das estações-grade NASA POWER já criadas. |
| `clima.nasa_power.ingerir_observacoes` | sob demanda | Cria a estação-grade da fazenda (se preciso) e busca a série diária. |
| `qualidade.despachar_avaliacoes` | semanal (domingo, 04h) | Enfileira `avaliar_fazenda` para todas as fazendas. |
| `qualidade.avaliar_fazenda` | sob demanda (ou via API) | Avalia representatividade por variável e aciona o fallback NASA POWER se preciso. |
| `satelite.despachar_descoberta` | diário (07h) | Enfileira `descobrir_cenas` para todas as fazendas. |
| `satelite.descobrir_cenas` | sob demanda | Busca cenas Sentinel-2 L2A novas (STAC) para uma fazenda; filtra por nuvem e despacha `processar_cena_area` por área intersectada. |
| `satelite.processar_cena_area` | sob demanda | Recorta, mascara (SCL) e calcula NDVI/EVI de uma cena para uma área produtiva; grava rasters + métricas. |
| `satelite.despachar_processamento_pendente` | a cada 6h | Rede de segurança: redespacha pares (cena, área) sem `indice_vegetacao_area` ainda. |
| `analise_temporal.despachar_tendencias` | semanal (segunda, 06h30) | Enfileira `calcular_tendencia_area` para todo par (área, tipo) — a janela recente desliza no tempo mesmo sem cena nova. |
| `analise_temporal.calcular_tendencia_area` | sob demanda (encadeada após `processar_cena_area`, ou via API) | Calcula tendência recente + comparação sazonal de NDVI/EVI de uma área e grava o snapshot mais recente. |

O worker acessa o Postgres via SQLAlchemy Core (tabelas refletidas), não via
os models ORM da API — os dois pacotes definem um módulo `app` de mesmo
nome e não podem ser importados um pelo outro no mesmo processo.

### 4. Web app

```bash
cd apps/web
cp .env.example .env
npm install
npm run dev
```

Abre em `http://localhost:5173`. A tela de Mapa lê fazendas e áreas
produtivas da API; as demais 7 telas prioritárias existem como rotas
navegáveis, ainda sem funcionalidade (dependem de fases futuras — cada
placeholder indica de qual fase depende).

## Endpoints de meteorologia (Fase 2)

- `GET /meteorologia/observacoes?estacao_id=|fazenda_id=&variavel=&inicio=&fim=`
  — com `fazenda_id`, resolve a(s) estação(ões) via `avaliacao_representatividade`.
- `GET /meteorologia/representatividade?fazenda_id=` — estação de referência
  e auxiliares por variável.
- `POST /meteorologia/representatividade/{fazenda_id}/reavaliar` — enfileira
  `qualidade.avaliar_fazenda` no worker (retorna 202; precisa do worker
  rodando para ser processado).

## Endpoints de vegetação (Fase 3)

- `GET /vegetacao/indices?area_produtiva_id=&tipo=&inicio=&fim=` — série de
  NDVI/EVI de uma área, com o campo derivado `redundante` (`true` quando a
  cena de origem foi marcada `REDUNDANTE` por outra do mesmo dia cobrindo a
  mesma parte da área — a linha nunca é apagada, só deixa de ser a leitura
  principal do dia).
- `GET /vegetacao/cenas?fazenda_id=&inicio=&fim=` — catálogo de cenas
  Sentinel-2 que intersectam a fazenda, incluindo rejeitadas (nuvem acima
  do limiar) e redundantes — nunca apagadas, para a tela de Histórico
  ambiental poder mostrar lacunas e o porquê.

## Endpoints de análise temporal (Fase 4)

- `GET /vegetacao/tendencia?area_produtiva_id=&tipo=` — snapshot mais
  recente da tendência (janela móvel) e comparação sazonal de NDVI/EVI de
  uma área.
- `POST /vegetacao/tendencia/{area_produtiva_id}/recalcular` — enfileira
  `analise_temporal.calcular_tendencia_area` para NDVI e EVI (retorna 202).
- `GET /vegetacao/lacunas?area_produtiva_id=&tipo=&inicio=&fim=` —
  intervalos sem observação `qualidade=suficiente` acima do limiar
  configurado (`vegetacao_limiar_gap_dias`), calculados na leitura.
- `GET /meteorologia/lacunas?estacao_id=|fazenda_id=&variavel=&inicio=&fim=`
  — mesma detecção de lacunas para a série meteorológica resolvida (limiar
  `meteorologia_limiar_gap_dias`).

## Testes

```bash
cd workers/geo
source .venv/bin/activate
export DATABASE_URL="postgresql+psycopg://pecuaria:pecuaria@localhost:5432/pecuaria"
python -m pytest tests/ -v
```

Os testes de cliente HTTP (INMET/NASA POWER/STAC) usam respostas mockadas,
sem rede real. Os de ingestão/qualidade/satélite/análise temporal rodam
contra o Postgres local (pulados automaticamente se `DATABASE_URL` não
estiver acessível) e limpam os dados que criam ao final. Os de
`processing/raster_io.py` e `clients/storage.py` usam GeoTIFFs sintéticos e
um `moto` local (`ThreadedMotoServer`) — nenhum COG real é baixado nem
MinIO real é necessário para rodar a suíte.

A API também tem sua própria suíte (por enquanto só lógica pura, sem
banco):

```bash
cd apps/api
source .venv/bin/activate
python -m pytest tests/ -v
```
