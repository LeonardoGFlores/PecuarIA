# SPEC — PecuarIA: Ferramenta de Análise de Cenários Pecuários

## Contexto

Produtores rurais e consultores de pecuária precisam decidir, com frequência,
entre diferentes formas de produção — pasto, confinamento, semi-intensivo,
ciclo completo/cria/recria/engorda — mas essa análise costuma ser feita de
forma manual em planilhas soltas, sem padronização, o que dificulta comparar
cenários de forma rápida, confiável e repetível.

O PecuarIA é uma ferramenta independente onde fazendas e clientes se
cadastram e simulam, eles mesmos, diferentes cenários de produção (bovino de
corte e leite na v1), projetando custos, desempenho zootécnico, receita e
resultado financeiro, para decidir qual sistema de produção adotar.

**Para quem**: fazendas/clientes finais (self-service, cada um com sua conta
e seus dados isolados) — não apenas o Leonardo ou seus clientes de
consultoria operando a ferramenta em nome deles.

## Requisitos

### P0 (v1 — obrigatório para lançar)

- **Autenticação e multi-tenant**: cadastro/login por fazenda, com
  isolamento de dados entre fazendas (Row Level Security).
- **Modelo de domínio** para bovino de **corte** e **leite**, cobrindo os
  sistemas: pasto, confinamento, semi-intensivo, e as fases cria/recria/
  engorda/ciclo completo (adaptado por espécie).
- **Motor de cálculo determinístico** cobrindo:
  - Custos operacionais: fixos e variáveis (mão de obra, insumos, sanidade,
    arrendamento/depreciação de área e instalações).
  - Desempenho zootécnico: GMD (ganho médio diário) ou produção de leite/dia,
    conversão alimentar, mortalidade, duração do ciclo.
  - Receita e preço de venda: preço projetado (arroba do boi, litro do
    leite), receita bruta.
  - Indicadores de investimento: lotação (cab/ha), área necessária, CAPEX
    inicial, fluxo de caixa ao longo do ciclo, payback.
- **Análise de sensibilidade**: variar premissas-chave (preço, GMD, custo) e
  visualizar o impacto no resultado; cenários otimista/realista/pessimista.
- **CRUD de cenários**: criar, editar, duplicar e excluir cenários, em
  número **ilimitado** por fazenda.
- **Comparação lado a lado**: tabela comparando N cenários simultaneamente
  (custos, indicadores zootécnicos, resultado financeiro).
- **Dashboard com gráficos**: visualização comparativa entre cenários e da
  análise de sensibilidade.
- **Preços de mercado com integração automática**: busca periódica de
  preços de referência (arroba do boi, leite, milho) a partir de fonte
  pública (ex.: CEPEA), com **fallback de edição manual** quando a
  integração falhar ou não cobrir um índice necessário.
- **Unidades e moeda**: Brasil — Real (R$), arroba (15 kg), hectare, kg.

### P1 (evolução natural, não bloqueia o lançamento)

- Espécies adicionais: ovino/caprino, reaproveitando o motor genérico já
  construído para corte/leite.
- Exportação de relatório em PDF por cenário/comparação.
- Provedor de preços alternativo/pago, como contingência caso o scraping da
  fonte pública se mostre instável.
- Histórico/série temporal de preços de mercado exibido no dashboard.
- Modelo de negócio (planos pagos, cobrança via Stripe) caso a validação de
  uso justifique monetizar.

### P2 (futuro, sem compromisso de data)

- Simulação probabilística (Monte Carlo) como modo alternativo ao
  determinístico.
- Múltiplos usuários por fazenda, com permissões (equipe).
- Aplicativo mobile nativo ou PWA otimizado para uso offline.
- Benchmarking anônimo entre fazendas (comparar o próprio cenário com
  médias regionais/setoriais, respeitando privacidade).
- Integração com sistemas de gestão de rebanho já usados pelo cliente
  (importação de dados existentes).

## Fora de escopo

- Gestão operacional de rebanho no dia a dia (isto não é um ERP
  agropecuário — é uma ferramenta de simulação e comparação de cenários).
- Rastreabilidade sanitária e protocolos veterinários detalhados.
- Emissão fiscal/contábil (notas fiscais, apuração de impostos).
- Espécies fora do domínio bovino/ovino-caprino (aves, suínos etc.).
- Cobrança/billing na v1 (ferramenta gratuita por enquanto).

## Stack escolhida

**Next.js (React + TypeScript) com Tailwind/shadcn no front-end, e Supabase
(Postgres + Auth + Row Level Security + Edge Functions) no back-end.**

Essa combinação resolve nativamente os dois requisitos mais caros do
projeto: multi-tenant seguro por fazenda (Auth + RLS do Supabase, sem
precisar montar isolamento de dados na mão) e um job agendado para buscar
preços de mercado (Edge Function + cron do Supabase, sem infraestrutura
própria). O motor de cálculo é determinístico e leve o suficiente para
rodar inteiro no cliente em TypeScript puro, dando resposta instantânea na
análise de sensibilidade ("e se") sem round-trip ao servidor a cada ajuste
de premissa — gráficos ficam a cargo do Recharts, e o deploy no Vercel é o
par natural do Next.js.
