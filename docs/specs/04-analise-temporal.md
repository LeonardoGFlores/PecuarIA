# 04 — Análise temporal

## Contexto

As docs 02 e 03 já anteciparam parte desta fase e adiaram deliberadamente sua implementação:
- Doc 02 (processamento NDVI/EVI), passos 11–12, definiu como P1 ("etapa separada, não bloqueia
  a gravação do registro bruto") a tendência recente por janela móvel, a comparação com o mesmo
  período em anos anteriores, e a detecção explícita de lacunas na série de
  `indice_vegetacao_area` — sem implementar nada disso na Fase 3.
- Doc 03 (motor de diagnóstico de gargalos), na tabela de cruzamentos, lista "precipitação
  recente" e "estação do ano" como cruzamentos obrigatórios para o sinal "Queda de NDVI/EVI" —
  mas esse motor só é implementado na Fase 6, depois que meteorologia e vegetação já tiverem
  histórico real suficiente para calibrar qualquer limiar.

Este documento fecha a tendência/sazonalidade de vegetação (o que a doc 02 deixou pendente) e a
detecção de lacunas para as duas séries (vegetação e meteorologia). Ele **não** cobre
tendência/sazonalidade de clima — ver "Fora de escopo".

Importante: este documento produz apenas **estatística descritiva** sobre séries já persistidas
(tendência, variação, lacuna). Ele nunca produz um julgamento diagnóstico ("isso é um problema",
"isso é degradação") — essa responsabilidade é exclusiva do motor de diagnóstico (doc 03, Fase
6), que cruza esta saída com outras camadas antes de qualquer conclusão.

## Requisitos

### P0 — sem isso não serve
- Tendência e comparação sazonal nunca recalculam nem sobrescrevem os registros brutos de
  `indice_vegetacao_area` — são uma camada derivada, à parte, sobre dado já gravado (mesmo
  princípio do doc 02: nunca alterar a evidência original).
- Só entram no cálculo de tendência de vegetação linhas com `qualidade=suficiente`; linhas
  `insuficiente` contam como ausência de observação, nunca como zero.
- Toda tendência de vegetação persistida gera um registro no manifesto de execução
  (`execucao_processamento`, doc 00) — com as fontes, período e versão do algoritmo usados.
- Detecção de lacunas nunca interpola ou preenche — apenas sinaliza o intervalo sem observação
  válida explicitamente na resposta da API.
- Classificação de tendência (`queda`/`estável`/`alta`) é estritamente estatística (magnitude e
  direção da variação) — nunca atribui causa. Uma queda por colheita/pastejo recente (caso de
  borda já registrado na doc 02) ainda é classificada como `queda`; a explicação fica para o
  motor de diagnóstico.

### P1 — importante, mas não bloqueia
- Detecção de lacunas também para a série meteorológica (`observacao_meteorologica`) — mesmo
  princípio da vegetação, custo de implementação baixo por reusar a mesma função de varredura.

### P2 — bom ter
- Tendência/sazonalidade de precipitação (não apenas lacunas) — adiado para quando o motor de
  diagnóstico (Fase 6) precisar de mais do que um agregado simples de chuva recente.

## Pipeline

Dois fluxos independentes, sem dependência um do outro:

### A. Tendência de vegetação (persistida)

1. Para uma `(area_produtiva_id, tipo)` (NDVI ou EVI), busca as linhas de
   `indice_vegetacao_area` com `qualidade=suficiente` cuja `data_aquisicao` cai nos últimos N
   dias (janela configurável, default 90).
2. Se o número de amostras na janela for menor que o mínimo configurável (default 5), grava
   `classificacao=dados_insuficientes` e todos os demais campos numéricos como `null` — nunca
   estima uma tendência a partir de poucos pontos.
3. Calcula a inclinação da série (valor por dia) por mínimos quadrados sobre `(dia, mediana)` da
   janela, e a variação percentual entre o início e o fim do período coberto pelas amostras.
4. Classifica: `queda` se a variação percentual for menor que `-limiar` (default -10%), `alta`
   se maior que `+limiar`, `estável` caso contrário.
5. Busca a mesma janela de dias no ano anterior (mesmo período do calendário, com tolerância
   configurável de dias, default 15). Se houver amostras suficientes (mínimo configurável,
   default 3) nesse período também, calcula a variação sazonal (valor médio do período atual vs.
   o do ano anterior) e marca `comparacao_sazonal_disponivel=true`; senão, marca `false` e deixa
   os campos sazonais `null`.
6. Grava (upsert por `area_produtiva_id`+`tipo`) em `tendencia_vegetacao_area` — uma linha por
   par, sempre reescrita com o cálculo mais recente (não historizada).
7. Toda a execução acontece dentro de `rastrear_execucao` (manifesto), com
   `tipo=tendencia_vegetacao`.

### B. Detecção de lacunas (calculada na leitura, não persistida)

1. Para a série já filtrada (vegetação: `qualidade=suficiente`; meteorologia: série resolvida
   pela API para a fazenda/variável pedida), extrai as datas com observação válida, ordenadas.
2. Varre a lista: qualquer intervalo entre duas datas consecutivas (ou entre a última data e o
   fim de referência, hoje por padrão) maior que o limiar configurável (vegetação: 15 dias;
   meteorologia: 7 dias) vira uma lacuna reportada.
3. Nenhum valor é preenchido — a lacuna é só um intervalo `(início, fim, dias)` na resposta.

## Casos de borda a tratar

| Caso | Comportamento esperado |
|---|---|
| Janela recente sem amostras suficientes | `classificacao=dados_insuficientes`; campos numéricos `null` — nunca omitido nem zero. |
| Janela cruza colheita/pastejo recente (queda legítima) | Ainda classificada como `queda` — o pipeline não distingue causa; isso é papel do motor de diagnóstico (Fase 6). |
| Área sem nenhuma observação suficiente no mesmo período do ano anterior | `comparacao_sazonal_disponivel=false`; campos sazonais `null` — nunca estimado por interpolação. |
| Lacuna aberta até o presente (satélite ou estação atualmente sem dado) | A lacuna se estende até a data de referência (hoje, ou `fim` do filtro), não apenas até a penúltima observação. |
| Série de clima resolvida por fazenda mistura estação `observado` (referência/auxiliar) e `estimado` (grade NASA POWER) | A lacuna é calculada sobre a série já resolvida e exposta pela API (a mesma que o usuário vê), não sobre a estação de referência isolada — decisão registrada abaixo, não um bug. |

## Lacunas identificadas

- Os limiares numéricos (janela de 90 dias, faixa de ±10% para "estável", tolerância sazonal de
  ±15 dias, mínimo de 5 amostras na janela recente e 3 na sazonal, limiar de lacuna de 15 dias
  para vegetação e 7 para meteorologia) são defaults de implementação inicial, sem calibração
  contra dado real — mesma ressalva já registrada nas docs 02 e 03 para os limiares delas.
  Ficam como variável de ambiente/configuração, não constante fixa, para ajuste sem deploy de
  código novo.
- A doc 00 (arquitetura), na tabela componente→stack, descreve "análise temporal" como "módulo
  Python no worker (pandas) consumido pela API" — essa frase não se sustenta literalmente, já
  que a API e o worker não podem se importar (dois pacotes chamados `app`, ver docstring de
  `workers/geo/app/db.py`). O padrão real seguido aqui é o mesmo já usado por
  `avaliacao_representatividade` desde a Fase 2: o worker calcula e persiste, a API lê via seu
  próprio ORM. Para detecção de lacunas — que este documento decide não persistir, por ser
  barata de recalcular a cada leitura — esse padrão não se aplica: a lógica fica inteiramente na
  API, por necessidade arquitetural, não por escolha estética.
- Detecção de lacunas de clima sobre a série resolvida por fazenda pode mascarar uma lacuna real
  da estação local se o fallback em grade (NASA POWER) estiver preenchendo o período — decisão
  deliberada (ver casos de borda), pendente de revisão se um usuário precisar ver especificamente
  a continuidade da estação de referência isolada.
- `tendencia_vegetacao_area` não é historizada (upsert único por área+tipo) — se uma fase futura
  precisar da evolução da própria classificação de tendência ao longo do tempo, isso exige uma
  tabela nova; não há consumidor para isso hoje.

## Fora de escopo

- Tendência e comparação sazonal de precipitação/temperatura/demais variáveis meteorológicas —
  só a detecção de lacunas é implementada para o clima nesta fase. Se o motor de diagnóstico
  (Fase 6) precisar de mais do que um agregado simples de chuva recente, isso é lacuna real a
  revisitar, não um esquecimento.
- Qualquer correlação entre camadas (ex.: cruzar queda de NDVI com precipitação) — isso é
  exclusivamente o motor de diagnóstico, doc 03, Fase 6.
- Qualquer interface (tela) que consuma estes dados.
