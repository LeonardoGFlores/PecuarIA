# 01 — Contrato de dados das fontes

## Contexto

Antes de qualquer diagnóstico ou simulação de cenário, o sistema precisa de um modelo de dados
comum para as 5 camadas de evidência da fazenda (território, meteorologia, vegetação,
perfil humano, oferta regional). Sem um contrato único, cada camada acumula seu próprio formato
e o diagnóstico (doc 03) não consegue cruzar evidências de origens diferentes com confiança.
Este documento é a base sobre a qual a Fase 1 (scaffold territorial + catálogo de fontes) e as
Fases 2–6 (ingestão, NDVI/EVI, diagnóstico) são construídas.

## Requisitos

### P0 — sem isso não serve
- Todo registro de evidência carrega proveniência completa: fonte, localização, período,
  unidade, qualidade, data de obtenção e versão de processamento.
- Todo registro é classificado como **Observado**, **Derivado**, **Estimado**, **Declarado** ou
  **Hipótese** — essa classificação é um campo de primeira classe, não uma inferência da
  interface.
- Geometrias (fazenda, área produtiva, ponto de infraestrutura, footprint de cena) são
  armazenadas como tipos espaciais nativos (PostGIS), nunca como texto/JSON sem índice espacial.
- Nenhuma tabela de catálogo de fonte (estação, cena de satélite, fornecedor) pode existir sem
  campo de rastreabilidade de origem (`fonte` + identificador externo, quando houver).

### P1 — importante, mas não bloqueia
- Histórico de mudança de uso de área é versionado (nunca sobrescrito) — uma alteração de uso
  gera um novo registro com vigência, preservando o anterior.
- Preço de referência é modelado como um campo distinto de "oferta disponível" — nunca
  confundidos na mesma tabela sem um campo que os diferencie.

### P2 — bom ter
- Campos de qualidade (`qualidade`) seguem uma escala comum entre camadas (ex.: alta / média /
  baixa / insuficiente) para permitir comparação cruzada na tela de Diagnóstico.

## Mixin de proveniência (comum a toda tabela de evidência)

Todas as tabelas descritas abaixo herdam estes campos, além dos seus campos específicos:

| Campo | Tipo | Descrição |
|---|---|---|
| `fonte` | string | Identificador da origem (ex.: `INMET`, `NASA_POWER`, `SENTINEL2_L2A`, `declarado_produtor`, `cotacao_fornecedor`). |
| `status` | enum | `observado` \| `derivado` \| `estimado` \| `declarado` \| `hipotese`. |
| `qualidade` | enum | `alta` \| `media` \| `baixa` \| `insuficiente`. |
| `data_obtencao` | timestamp | Quando o dado entrou no sistema (não confundir com a data do fenômeno observado). |
| `versao_processamento` | string | Versão do pipeline/algoritmo que gerou o registro, quando aplicável (`null` para dado bruto declarado). |
| `unidade` | string | Unidade de medida, quando aplicável. |
| `periodo_inicio` / `periodo_fim` | timestamp | Período que o registro cobre (podem ser iguais para um instante). |

### Classificação de status — critério de uso

- **Observado**: medição direta de um sensor/fonte primária (chuva registrada por uma estação,
  reflectância de uma cena de satélite).
- **Derivado**: cálculo determinístico sobre uma ou mais observações (NDVI calculado a partir
  de bandas; mediana de uma série).
- **Estimado**: saída de um modelo com incerteza (dado em grade como NASA POWER preenchendo uma
  lacuna; uma previsão).
- **Declarado**: informação fornecida pelo produtor, equipe ou fornecedor, sem verificação
  independente (capital disponível, quantidade de pessoas na equipe, cotação recebida por
  telefone).
- **Hipótese**: explicação candidata ainda não confirmada, produzida pelo motor de diagnóstico
  (doc 03) — nunca uma medição.

## A. Território e estrutura da fazenda

| Tabela | Campos principais | Observações |
|---|---|---|
| `fazenda` | `id`, `nome`, `proprietario`, `geom` (Polygon, perímetro), `area_total_ha`, `versao` | `versao` incrementa a cada edição de perímetro; a versão anterior não é apagada (fica em `fazenda_historico`). |
| `area_produtiva` | `id`, `fazenda_id`, `nome`, `geom` (Polygon), `tipo_uso` (`pasto`\|`mata`\|`agua`\|`lavoura`\|`infraestrutura`\|`outro`), `area_ha`, `area_utilizavel_ha`, `sistema_produtivo` (`corte`\|`leite`\|`agricultura`\|`misto`\|`nao_definido`) | `area_utilizavel_ha` é sempre ≤ `area_ha`; a diferença deve ter explicação (ex.: benfeitoria, área alagada). |
| `historico_uso_area` | `id`, `area_produtiva_id`, `uso`, `vigencia_inicio`, `vigencia_fim` (null = vigente), `declarado_por`, `fonte` | Nunca é atualizado in-place; nova vigência fecha a anterior. |
| `ponto_infraestrutura` | `id`, `fazenda_id`, `tipo` (`agua`\|`curral`\|`cerca`\|`galpao`\|`acesso`\|`outro`), `geom` (Point ou LineString), `atributos` (jsonb livre por tipo) | Estradas e cercas usam LineString; pontos de água e currais usam Point. |

Regra explícita: um índice de vegetação elevado numa área não implica automaticamente
disponibilidade de pasto — `tipo_uso` e `sistema_produtivo` são o que distingue vegetação
produtiva de mata/água/outra superfície antes de qualquer leitura de NDVI/EVI (ver doc 02 e 03).

## B. Meteorologia regional

| Tabela | Campos principais | Observações |
|---|---|---|
| `estacao_meteorologica` | `id`, `fonte` (`INMET`\|`NASA_POWER`\|`outra`), `codigo_externo`, `nome`, `geom` (Point), `altitude_m`, `operador`, `tipo` (`observado`\|`grade`), `variaveis_disponiveis` (array), `periodo_inicio_serie`, `periodo_fim_serie` | `tipo=grade` marca fontes como NASA POWER — nunca tratadas como medição local na interface. |
| `observacao_meteorologica` | `id`, `estacao_id`, `variavel` (`precipitacao`\|`temperatura`\|`umidade_relativa`\|`radiacao`\|`vento`), `timestamp`, `valor`, `unidade`, `flag_qualidade` | Uma linha por variável/timestamp/estação; falhas de estação viram gaps, nunca são interpoladas nesta tabela. |
| `avaliacao_representatividade` | `id`, `fazenda_id`, `estacao_id`, `variavel`, `distancia_km`, `criterio_completude`, `criterio_atualizacao`, `criterio_consistencia`, `papel` (`referencia`\|`auxiliar`) | Avaliada **por variável** — uma estação pode ser referência para temperatura e auxiliar para chuva. |

Regras explícitas herdadas da spec de produto:
- Nunca escolher automaticamente a estação mais próxima sem avaliar completude, atualização e
  consistência.
- Interpolação espacial entre estações só é introduzida com validação — não existe cálculo de
  média entre estações nesta fase.
- Dados em grade (NASA POWER) preenchem lacunas de contexto e são sempre marcados
  `status=estimado`, `tipo=grade` — nunca reclassificados como medição local.

## C. Vegetação por NDVI e EVI

| Tabela | Campos principais | Observações |
|---|---|---|
| `cena_satelite` | `id`, `fonte` (`SENTINEL2_L2A`), `tile_id`, `data_aquisicao`, `cobertura_nuvem_cena_pct`, `geom` (Polygon, footprint), `status_processamento` (`pendente`\|`processada`\|`rejeitada`) | `data_aquisicao` é a data real de captura pelo satélite, não a data de processamento. |
| `indice_vegetacao_area` | `id`, `area_produtiva_id`, `cena_id`, `tipo` (`NDVI`\|`EVI`), `data_aquisicao`, `cobertura_valida_pct`, `mediana`, `p10`, `p25`, `p75`, `p90`, `desvio_padrao`, `versao_processamento`, `raster_ref` (path no storage de objetos) | `cobertura_valida_pct` é medida **dentro da área produtiva**, não da cena inteira. Registro só é gravado como `status=derivado` quando cobertura ≥ limiar mínimo (ver doc 02); abaixo disso, o gap fica registrado e não silenciado. |

Ver doc 02 para o pipeline completo de geração desses registros (máscara de nuvem, escala/
offset, fórmulas, limiar de cobertura válida, casos de borda).

## D. Perfil do produtor e da equipe

Todas as tabelas desta camada são `status=declarado` por definição — não há medição
independente.

| Tabela | Campos principais |
|---|---|
| `perfil_produtor` | `id`, `fazenda_id`, `objetivos` (array: `renda`\|`estabilidade`\|`expansao`\|`intensificacao`\|`diversificacao`), `capital_disponivel`, `limite_investimento`, `capital_giro`, `tolerancia_risco` (`baixa`\|`media`\|`alta`), `disponibilidade_gestao_horas_semana` |
| `equipe` | `id`, `fazenda_id`, `quantidade_pessoas`, `funcoes` (array), `disponibilidade_sazonal` (jsonb por época do ano), `competencias` (array), `apoio_tecnico` (`proprio`\|`contratado`\|`nenhum`) |

Regra explícita: o sistema não produz uma nota genérica de "qualidade do produtor". Essas
tabelas existem para que o motor de cenários (Fase 7) compare exigência de manejo de uma
alternativa contra a capacidade aqui declarada — a comparação é feita no motor de cenários, não
nesta camada.

## E. Oferta regional de animais, insumos e serviços

| Tabela | Campos principais | Observações |
|---|---|---|
| `fornecedor` | `id`, `nome`, `tipo` (`animais`\|`insumos`\|`servicos`\|`frete`\|`comprador`), `regiao`, `contato` | |
| `oferta_regional` | `id`, `fornecedor_id`, `categoria`, `especificacao`, `unidade`, `quantidade_disponivel`, `quantidade_minima`, `preco`, `condicoes`, `sazonalidade`, `data_registro`, `validade_cotacao`, `fonte` | Uma oferta com `validade_cotacao` vencida não é elegível para simulação de cenário (ver doc de cenários, fora do escopo desta entrega) — fica retida como histórico. |
| `logistica_oferta` | `id`, `oferta_id`, `distancia_km`, `prazo_entrega_dias`, `custo_frete` | O custo relevante para cenários é o custo entregue na fazenda: `preco` + `custo_frete`, nunca `preco` isolado. |

Regra explícita: preço de referência (sem fornecedor, quantidade ou validade associados) não é
tratado como oferta disponível — não é modelado nesta tabela; se for necessário registrar preço
de referência de mercado, isso é uma tabela separada e futura, fora do escopo desta fase.

## Lacunas identificadas

- `observacao_meteorologica` e `indice_vegetacao_area` são migradas nesta fase mas ficam vazias
  — populadas somente quando a ingestão (Fase 2) e o processamento NDVI/EVI (Fase 3) forem
  implementados. Não cadastrar essas tabelas agora geraria retrabalho de schema mais tarde.
- `cena_satelite.status_processamento` existe desde já para permitir que a Fase 3 marque cenas
  rejeitadas (ex.: 100% de nuvem) sem precisar de uma migration adicional.

## Fora de escopo

- Regras do motor de diagnóstico e do motor de cenários (docs separados / fases futuras).
- Autenticação e permissão de acesso por usuário/fazenda.
- Tabela de preço de referência de mercado (distinta de oferta) — mencionada acima como
  possível necessidade futura, não implementada aqui.
