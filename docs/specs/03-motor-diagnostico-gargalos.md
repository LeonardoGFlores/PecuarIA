# 03 — Motor de identificação de gargalos

## Contexto

O diagnóstico não pode transformar um sinal isolado (ex.: "NDVI baixo") diretamente em uma
conclusão (ex.: "pasto degradado"). Ele precisa cruzar contexto, persistência e evidências de
várias camadas antes de registrar uma hipótese, e sempre separar impacto potencial de grau de
confiança. Este documento formaliza o fluxo de 7 etapas e o modelo de dados da spec de produto,
para implementação na Fase 6 do roadmap, depois que meteorologia (Fase 2) e NDVI/EVI (Fase 3)
já estiverem alimentando dados reais.

## Requisitos

### P0 — sem isso não serve
- Nenhuma conclusão é gerada sem passar pelas 7 etapas do fluxo abaixo — não existe atalho de
  "sinal direto vira gargalo".
- Impacto potencial e grau de confiança/sustentação da hipótese são campos **separados**; nunca
  combinados em uma nota única. Um gargalo pode ter alto impacto e baixa evidência.
- Toda hipótese registra o que falta para ser confirmada ou descartada (`dados_faltantes`).
- Toda regra de cruzamento é declarativa e auditável (tabela de regras versionada em código),
  não um modelo estatístico opaco.

### P1 — importante, mas não bloqueia
- Gargalos têm responsável e acompanhamento (status de verificação), permitindo que o usuário
  saiba o que já foi investigado e o que ainda está pendente.
- Explicações esperadas (colheita, pastejo, mudança de uso, sazonalidade) são checadas antes de
  registrar uma hipótese de anomalia — reduz falso positivo por comportamento normal do sistema
  produtivo.

### P2 — bom ter
- Priorização automática de qual gargalo inspecionar primeiro, combinando impacto potencial e
  facilidade de verificação.

## Fluxo de diagnóstico (7 etapas)

1. **Detectar um sinal ou incompatibilidade** — ex.: queda de NDVI/EVI, desempenho diferente
   entre áreas comparáveis, dependência de suplementação num cenário simulado.
2. **Verificar a qualidade dos dados** que originaram o sinal (cobertura válida da cena,
   representatividade da estação, completude da série) — um sinal sobre dado `qualidade=
   insuficiente` não avança para hipótese, fica registrado como "dado insuficiente para
   diagnosticar".
3. **Verificar explicações esperadas**: colheita/pastejo recente (via `historico_uso_area`),
   mudança de uso registrada, sazonalidade conhecida da região (via série meteorológica). Se uma
   explicação esperada cobre o sinal, ele é registrado como comportamento normal, não como
   gargalo.
4. **Identificar evidências adicionais** nas outras camadas (clima, uso, manejo declarado,
   oferta regional) que sustentem ou refutem hipóteses candidatas.
5. **Registrar hipóteses compatíveis** com as evidências reunidas — pode haver mais de uma
   hipótese candidata simultânea para o mesmo sinal.
6. **Definir o que falta para confirmar** cada hipótese (`dados_faltantes`): inspeção de campo,
   dado de outra fonte, período adicional de observação.
7. **Priorizar inspeção ou ação** com base em impacto potencial e facilidade/custo de
   verificação.

## Tabela de cruzamentos (regras declarativas)

| Sinal | Cruzamentos obrigatórios | Saída possível |
|---|---|---|
| Queda de NDVI/EVI | Precipitação recente, estação do ano, `tipo_uso`/`sistema_produtivo`, `historico_uso_area` | Anomalia vegetativa a investigar (se não explicada por colheita/pastejo/sazonalidade) |
| Recuperação lenta após chuva | Histórico da área, `historico_uso_area`, observação de campo declarada | Possível limitação de recuperação (hipótese, não conclusão) |
| Desempenho diferente entre áreas comparáveis | `tipo_uso`, solo/relevo (quando disponível), manejo declarado | Área prioritária para inspeção |
| Cenário depende de suplementação | Oferta regional (`oferta_regional`), logística (`logistica_oferta`), capital (`perfil_produtor`) | Gargalo de abastecimento |
| Intensificação exige mais trabalho | `equipe` (quantidade, disponibilidade sazonal), calendário de tarefas do cenário | Gargalo de capacidade operacional |
| Compra de animais necessária | Categoria/época/disponibilidade em `oferta_regional`, logística | Restrição regional de reposição |

Cada linha desta tabela é implementada como uma regra nomeada e testável isoladamente — a
adição de uma nova regra não deve exigir alterar as demais.

## Modelo de dados

| Tabela | Campos principais |
|---|---|
| `sinal_detectado` | `id`, `tipo`, `area_produtiva_id` ou `fazenda_id`, `periodo_inicio`, `periodo_fim`, `severidade`, `dados_origem` (referências aos registros de evidência que geraram o sinal) |
| `gargalo` | `id`, `sinal_id`, `localizacao` (área/fazenda), `periodo`, `impacto_potencial` (`baixo`\|`medio`\|`alto`), `status` (`aberto`\|`em_verificacao`\|`confirmado`\|`descartado`), `responsavel`, `proxima_verificacao` |
| `hipotese_gargalo` | `id`, `gargalo_id`, `descricao`, `grau_sustentacao` (`baixo`\|`medio`\|`alto`), `evidencias` (referências), `dados_faltantes` (texto/array) |

`impacto_potencial` vive em `gargalo`; `grau_sustentacao` vive em cada `hipotese_gargalo` — a
separação de tabelas garante que múltiplas hipóteses concorrentes não herdem uma confiança
única do gargalo pai.

## Lacunas identificadas

- Este documento define a tabela de regras e o modelo de dados, mas não a implementação do
  motor em si — fica para a Fase 6 do roadmap, depois que existir série meteorológica e NDVI/EVI
  real para cruzar (Fases 2 e 3). Implementar o motor antes disso produziria hipóteses sem
  evidência real disponível.
- Critérios numéricos de "desempenho diferente entre áreas" (o que conta como diferença
  significativa) não são fixados aqui — dependem de calibração com dados reais coletados nas
  Fases 2–3, para evitar definir limiares arbitrários sem base empírica.

## Fora de escopo

- Implementação de código do motor nesta entrega — o scaffold atual não inclui
  `apps/api/app/diagnostics/`; ele é criado na Fase 6.
- Modelos de aprendizado de máquina para inferir causas — o motor é declarativo por decisão de
  produto (evita "caixa-preta" nas conclusões).
- Motor de cenários (consome a saída deste motor, mas é especificado separadamente na Fase 7).
