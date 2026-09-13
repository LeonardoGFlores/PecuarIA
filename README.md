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

Este repositório cobriu as Fases 1 e 2 do roadmap: cadastro territorial,
catálogo de fontes e integração meteorológica (INMET + NASA POWER como
fallback em grade, com avaliação de representatividade por variável). As
demais fases (NDVI/EVI, diagnóstico, cenários) ainda não têm código — apenas
a spec que as guia.

**Nomes de campo da API do INMET não confirmados**: o ambiente onde a Fase 2
foi implementada bloqueia acesso de rede a `apitempo.inmet.gov.br` e
`power.larc.nasa.gov` — os clients foram escritos com base em pesquisa e um
exemplo de terceiro, não em chamadas reais. Antes de rodar a ingestão INMET
contra dados de produção, valide `workers/geo/app/clients/inmet.py`
(constantes `CAMPO_CATALOGO_*` e `CAMPOS_VARIAVEL_DIARIA`) com uma chamada
real e ajuste se necessário.

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

## Testes

```bash
cd workers/geo
source .venv/bin/activate
export DATABASE_URL="postgresql+psycopg://pecuaria:pecuaria@localhost:5432/pecuaria"
python -m pytest tests/ -v
```

Os testes de cliente HTTP (INMET/NASA POWER) usam respostas mockadas, sem
rede real. Os de ingestão/qualidade rodam contra o Postgres local (pulados
automaticamente se `DATABASE_URL` não estiver acessível) e limpam os dados
que criam ao final.
