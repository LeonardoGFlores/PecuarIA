# 05 — Perfil do produtor e oferta regional (camadas D/E)

## Contexto

O doc 01 já definiu o schema das camadas D (perfil do produtor e da equipe) e E (oferta regional
de animais, insumos e serviços), migrado desde a Fase 1 junto com o restante do território e
catálogo de fontes. Faltava expor CRUD real sobre essas tabelas — até aqui só existia
`GET`/`POST /fontes/fornecedores`, o resto (perfil, equipe, oferta, logística, e o
completamento de fornecedor) só tinha schema de banco e model ORM, sem rota.

Este documento fecha essa lacuna. Diferente das fases anteriores, não há nenhuma lógica de
processamento, ingestão externa ou cálculo — é cadastro declarado direto pelo usuário, sem
worker envolvido. O que essas tabelas alimentam (comparar exigência de manejo de um cenário
contra a capacidade aqui declarada; cruzar gargalo de abastecimento com oferta regional
disponível) é trabalho do motor de cenários (Fase 7) e do motor de diagnóstico (Fase 6,
doc 03) — nenhum dos dois ainda existe, e esta fase não antecipa a lógica deles, só garante que
os dados que eles vão precisar já possam ser cadastrados e lidos corretamente.

## Requisitos

### P0 — sem isso não serve

- `perfil_produtor` e `equipe` são **singleton por fazenda** — no máximo uma linha de cada por
  `fazenda_id`. O doc 01 já trata essas tabelas no singular ("o perfil", "a equipe") e registra
  que são sempre `status=declarado`, estado atual, sem medição independente; esta fase torna
  essa leitura explícita com uma constraint de unicidade em `fazenda_id`, evitando ambiguidade
  sobre qual linha é a vigente quando o produtor edita seus dados.
- Nenhuma tabela desta camada usa o mixin de proveniência completo (`fonte`/`status`/
  `qualidade`/`data_obtencao`/...) — são dados declarados diretamente pelo usuário, não
  evidência observada/derivada/estimada. Isso já é assim no código hoje e deve continuar.
- Uma `oferta_regional` com `validade_cotacao` vencida nunca é apagada — fica retida como
  histórico (regra já registrada no doc 01). A API calcula e expõe um campo `vencida` na
  leitura, nunca persistido, mesmo padrão do campo `redundante` já usado em
  `IndiceVegetacaoRead` (Fase 3): dado derivado do relógio atual não é fato gravado.
- Apagar um `fornecedor` cascateia para suas `oferta_regional` e, por consequência, para a
  `logistica_oferta` de cada uma (`cascade="all, delete-orphan"` já declarado no ORM) — esse é o
  comportamento correto e intencional: sem o fornecedor, a oferta e sua logística não têm mais
  sentido próprio, diferente de uma evidência observacional que nunca se apaga.
- `fornecedor` ganha um campo `fonte` (novo — ver "Lacuna fechada" abaixo), sempre
  `"declarado_produtor"` nesta fase, já que um fornecedor é sempre cadastrado manualmente, nunca
  ingerido de uma fonte externa automatizada.

### P1 — importante, mas não bloqueia

Validações estruturais na escrita — nunca limiares de negócio calibrados, só limites físicos
inegociáveis (mesmo espírito da checagem `area_utilizavel_ha <= area_ha` já usada na Fase 1):

- Campos monetários/quantitativos (`capital_disponivel`, `limite_investimento`, `capital_giro`,
  `quantidade_pessoas`, `quantidade_disponivel`, `quantidade_minima`, `preco`, `distancia_km`,
  `prazo_entrega_dias`, `custo_frete`) rejeitam valores negativos quando informados.
- `quantidade_minima <= quantidade_disponivel`, quando ambos informados.
- `disponibilidade_gestao_horas_semana` entre 0 e 168 (horas em uma semana) — um limite físico,
  não um limiar de negócio.

### P2 — bom ter

- Nenhum item identificado para esta fase.

## Lacuna fechada: campo `fonte` em `fornecedor`

O requisito P0 do doc 01 (linha 22-23) exige que "nenhuma tabela de catálogo de fonte (estação,
cena de satélite, fornecedor) [exista] sem campo de rastreabilidade de origem (`fonte` +
identificador externo, quando houver)". A tabela `fornecedor`, porém, nunca teve esse campo —
nem na lista de campos do doc 01 (seção E), nem na migration da Fase 1. Esta fase fecha essa
lacuna: adiciona `fonte: str` a `Fornecedor`, com valor fixo `"declarado_produtor"` (não existe
hoje nenhum outro canal de cadastro de fornecedor além do usuário digitando os dados — se um
catálogo externo de fornecedores for integrado no futuro, o campo já existe e só precisa parar
de usar o valor fixo). O doc 01 é atualizado (seção E) para registrar o campo.

## Casos de borda a tratar

| Caso | Comportamento esperado |
|---|---|
| Fazenda sem `perfil_produtor`/`equipe` cadastrado | `GET` retorna 404 explícito — nunca um objeto vazio "fantasma" com campos nulos. |
| Segunda tentativa de `POST` de perfil/equipe para uma fazenda que já tem um | 409 — a mensagem indica usar `PUT` para atualizar o registro existente. |
| `oferta_regional.validade_cotacao` nula | Nunca classificada como `vencida` — ausência de prazo não é o mesmo que prazo expirado. |
| `fornecedor` sem nenhuma `oferta_regional` | Lista vazia na leitura, nunca erro. |
| `POST /fontes/ofertas` com `fornecedor_id` inexistente | 404, mesmo padrão de `criar_area_produtiva` validando `fazenda_id`. |
| `POST` de logística para uma oferta inexistente | 404. |

## Fora de escopo

- **Custo entregue** (`preco` + `custo_frete`) como campo calculado — o doc 01 já registra essa
  soma como "o custo relevante para cenários", mas uma oferta pode ter várias linhas de
  `logistica_oferta` (rotas/prazos diferentes); reduzir isso a um único número só faz sentido no
  contexto de uma simulação concreta. Isso é trabalho do motor de cenários (Fase 7); esta fase
  expõe `preco` e `custo_frete` separados e deixa a combinação para quem for consumir.
- Tabela de preço de referência de mercado (distinta de oferta) — já registrada como fora de
  escopo no doc 01, não implementada aqui.
- Qualquer regra de cruzamento entre perfil/equipe/oferta e as demais camadas (ex.: "cenário
  depende de suplementação", tabela de cruzamentos do doc 03) — isso é o motor de diagnóstico
  (Fase 6) e o motor de cenários (Fase 7), nenhum dos dois com código ainda.
- Autenticação/permissão por usuário — já fora de escopo da arquitetura (doc 00).
- Tela de Diagnóstico, Gargalos, Comparador de cenários e Relatório — dependem das fases acima.

## Lacunas identificadas

- Singleton por fazenda para `perfil_produtor`/`equipe` é uma decisão desta fase, não algo que
  já estava fixado no doc 01 original (que só registra que são tabelas "declaradas", sem falar
  em cardinalidade) — registrado aqui para não parecer um requisito antigo reinterpretado.
- As validações estruturais desta fase (não-negatividade, faixa de horas semanais) são limites
  físicos óbvios, não limiares de negócio calibrados — mesma ressalva já registrada nos docs
  02/03/04 para não fixar número de negócio sem dado real.
