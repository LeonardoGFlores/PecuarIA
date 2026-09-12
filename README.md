# PecuarIA

Painéis de controle

Plataforma de avaliação de fazendas: o que a fazenda pode produzir e o que está
limitando a operação atual, a partir de território, meteorologia, vegetação
(NDVI/EVI), perfil operacional e oferta regional. A especificação completa do
produto e a arquitetura estão em [`docs/specs/`](docs/specs/):

- [`00-arquitetura-e-stack.md`](docs/specs/00-arquitetura-e-stack.md) — componentes e stack.
- [`01-contrato-dados-fontes.md`](docs/specs/01-contrato-dados-fontes.md) — modelo de dados das 5 camadas de evidência.
- [`02-processamento-ndvi-evi.md`](docs/specs/02-processamento-ndvi-evi.md) — pipeline Sentinel-2 L2A.
- [`03-motor-diagnostico-gargalos.md`](docs/specs/03-motor-diagnostico-gargalos.md) — regras do motor de diagnóstico.

Este repositório está na Fase 1 do roadmap: cadastro territorial e catálogo de
fontes. As demais fases (meteorologia, NDVI/EVI, diagnóstico, cenários) ainda
não têm código — apenas a spec que as guia.

## Estrutura

```
apps/
  api/      # FastAPI: cadastro de fazenda/area_produtiva, catalogo de fontes, Alembic
  web/      # Vite + React + TypeScript + MapLibre GL
workers/
  geo/      # Celery: skeleton do worker de processamento geoespacial (Fase 3+)
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
export CELERY_BROKER_URL="redis://localhost:6379/0"
export CELERY_RESULT_BACKEND="redis://localhost:6379/1"
celery -A app.tasks worker --loglevel=info
```

Nesta fase o worker só tem uma task de exemplo (`geo.health_check`) — as
tasks de ingestão e processamento NDVI/EVI chegam nas Fases 2 e 3.

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
