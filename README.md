# PecuarIA — Busca e Análise de Clientes

Painéis de controle.

Aplicação para pesquisa e qualificação de clientes/leads: você define o
perfil desejado (nome, CNPJ, Instagram, Facebook, localização, segmento) e o
sistema consulta múltiplas fontes de dados em paralelo, agrega os resultados
em um perfil único e usa um agente interno (Claude) para gerar uma análise do
perfil e uma estratégia de abordagem para o time comercial.

## Arquitetura

Monorepo com dois pacotes npm (workspaces):

- **`server/`** — API Express + TypeScript. Cada fonte de dados é um
  "conector" independente e plugável (`server/src/connectors/`), todos com a
  mesma interface `SourceResult`. Os resultados são agregados
  (`server/src/analysis/aggregator.ts`) e passados ao agente de análise
  (`server/src/analysis/agent.ts`), que chama a API da Anthropic. Histórico
  de buscas é persistido em SQLite local (`server/data/pecuaria.sqlite`).
- **`web/`** — Frontend React + Vite. Formulário para definir o perfil de
  busca, visualização dos dados por fonte e da análise/estratégia gerada, e
  histórico de buscas anteriores.

## Fontes de dados

Todas as integrações usam **APIs oficiais**, nunca scraping — quando uma
fonte não tem credenciais configuradas, ela retorna claramente
`not_configured` em vez de simular dados.

| Fonte | API usada | Credenciais | Observações |
|---|---|---|---|
| CNPJ | [BrasilAPI](https://brasilapi.com.br) (espelho público da Receita Federal) | nenhuma | Requer o número do CNPJ; não existe API oficial gratuita para buscar CNPJ por nome da empresa. |
| Google | Custom Search JSON API | `GOOGLE_API_KEY`, `GOOGLE_CSE_ID` | Cria um mecanismo em https://programmablesearchengine.google.com/ |
| Instagram | Graph API — *Business Discovery* | `IG_BUSINESS_ACCOUNT_ID`, `IG_ACCESS_TOKEN` | Só retorna dados de contas **comerciais/criador públicas** (limitação da própria Meta; não existe API para perfis pessoais). Exige uma conta comercial própria conectada ao seu App do Meta. |
| Facebook | Graph API — Páginas | `FB_ACCESS_TOKEN` | Busca por nome/ID de Página pública. |

O agente de análise (Claude, via `@anthropic-ai/sdk`) usa `ANTHROPIC_API_KEY`.
Sem essa chave, a busca funciona normalmente, mas a análise e a estratégia
voltam com uma mensagem explicando que o agente não está configurado — os
dados brutos por fonte continuam disponíveis.

## Configuração

```bash
npm install
cp .env.example server/.env
# edite server/.env com as chaves que você tiver disponíveis
```

## Rodando em desenvolvimento

Em dois terminais:

```bash
npm run dev:server   # http://localhost:3001
npm run dev:web      # http://localhost:5173 (proxy para /api -> 3001)
```

## Testes e build

```bash
npm test              # testes do server (vitest)
npm run build          # build de produção de server + web
```

## Limitações conhecidas

- Instagram e Facebook só expõem dados via API oficial quando o perfil alvo
  é uma conta comercial/criador ou Página pública — não há forma legítima
  de consultar perfis pessoais fechados por API.
- A busca por CNPJ exige o número do documento; não há API gratuita oficial
  de busca por nome de empresa.
- O agente de análise nunca inventa dados: ele só analisa o que os
  conectores efetivamente retornaram, e sinaliza explicitamente quando uma
  fonte não respondeu ou não estava configurada.
