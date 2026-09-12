# 02 — Processamento NDVI/EVI

## Contexto

A camada C (vegetação) usa Sentinel-2 L2A como fonte inicial. NDVI e EVI são indicadores
espectrais, não medições diretas de produtividade — o pipeline precisa preservar essa distinção
em cada etapa, tratando nuvem, sombra e cobertura parcial como fatos a registrar, nunca a
esconder. Este documento detalha o pipeline que gera os registros de `indice_vegetacao_area`
definidos no doc 01, para implementação na Fase 3 do roadmap.

## Requisitos

### P0 — sem isso não serve
- Escala e offset do produto L2A são aplicados antes de qualquer cálculo de índice.
- Nuvem, sombra e pixels inválidos são mascarados usando a Scene Classification Layer (SCL) do
  próprio produto L2A — não um limiar heurístico sobre as bandas espectrais.
- Cobertura válida é medida **dentro do polígono da área produtiva**, não da cena inteira.
- Um pixel sem observação válida nunca é preenchido como "vegetação ruim" — fica como dado
  ausente (`null`), tanto no raster quanto nas estatísticas agregadas.
- A data registrada é a **data real de aquisição** da cena pelo satélite, nunca a data em que o
  processamento rodou.
- Toda execução é versionada: perímetro da área usado no recorte + versão do algoritmo de
  processamento ficam associados ao resultado (via `versao_processamento` e o manifesto de
  execução do doc 00).

### P1 — importante, mas não bloqueia
- Tendência recente e comparação com períodos sazonais equivalentes (ano anterior, mesma época)
  são calculadas como etapa separada da geração do índice bruto — não bloqueiam a gravação do
  registro se não houver histórico suficiente ainda.
- Lacunas no histórico (períodos sem observação válida) são expostas explicitamente na série
  temporal, não apenas omitidas.

### P2 — bom ter
- Detecção de resposta da vegetação após chuva/evento de manejo (cruzamento com a camada B) —
  depende do motor de diagnóstico (doc 03) e da série meteorológica já estarem disponíveis.

## Pipeline

1. **Descoberta de cenas** — busca diária por novas cenas Sentinel-2 L2A cujo footprint
   intersecta o perímetro da fazenda. Buscar diariamente não significa que haverá um mapa novo
   e válido todo dia (revisita do satélite + nuvem determinam isso).
2. **Filtro por nuvem da cena** — descartar cenas com `cobertura_nuvem_cena_pct` acima de um
   limiar configurável (padrão: 90%) antes de baixar bandas, para economizar processamento;
   cenas descartadas aqui são registradas com `status_processamento=rejeitada`, não apagadas.
3. **Download das bandas necessárias**:
   - NDVI: B04 (red), B08 (nir).
   - EVI: B02 (blue), B04 (red), B08 (nir).
   - Sempre: SCL (Scene Classification Layer), para máscara.
4. **Aplicar escala/offset** do produto L2A às bandas espectrais antes de qualquer cálculo
   (reflectância de superfície, conforme especificação do produto — não usar valores de
   contagem digital brutos).
5. **Máscara via SCL** — excluir pixels das classes: `3` (sombra de nuvem), `8`/`9` (nuvem de
   probabilidade média/alta), `10` (cirrus), `11` (neve/gelo). Classes de água (`6`) e solo
   exposto (`5`) não são mascaradas automaticamente — permanecem no dado bruto porque são
   informação sobre a área, não ruído de sensor.
6. **Recorte por área produtiva** — o cálculo é feito por polígono de `area_produtiva`, nunca
   pela fazenda inteira: uma média geral esconderia áreas com comportamento distinto.
7. **Cálculo dos índices** (após escala/offset e máscara aplicados):
   - `NDVI = (B08 - B04) / (B08 + B04)`
   - `EVI = G * (B08 - B04) / (B08 + C1*B04 - C2*B02 + L)`, com constantes padrão
     `G=2.5`, `C1=6`, `C2=7.5`, `L=1`.
8. **Cobertura válida** = percentual de pixels não mascarados dentro do polígono da área (não
   da cena). Se `cobertura_valida_pct` < limiar mínimo (padrão: 60%), o registro é gravado como
   `qualidade=insuficiente` e **não** é usado como se fosse uma leitura normal — nunca
   interpolado ou preenchido para parecer uma observação completa.
9. **Estatísticas por área**: mediana, percentis (p10/p25/p75/p90), desvio padrão, calculados
   apenas sobre pixels válidos.
10. **Persistência**:
    - Raster recortado e mascarado salvo no armazenamento de objetos, versionado por
      `area_produtiva_id` + `data_aquisicao` + `versao_processamento`.
    - Métricas + referência ao raster gravadas em `indice_vegetacao_area` (doc 01), com
      `data_aquisicao` real e `versao_processamento` do pipeline.
11. **Tendência e comparação sazonal** — etapa subsequente que lê a série já persistida:
    calcula tendência recente (janela móvel) e compara com o mesmo período em anos anteriores,
    quando houver histórico. Não recalcula nem sobrescreve os registros brutos.
12. **Detecção de lacunas** — qualquer intervalo de tempo sem registro `qualidade != insuficiente`
    acima de um limiar (ex.: 15 dias sem observação válida) é sinalizado explicitamente na série
    exposta pela API — nunca preenchido por interpolação implícita.

## Casos de borda a tratar (obrigatórios para os testes da Fase 8)

| Caso | Comportamento esperado |
|---|---|
| Área 100% coberta por nuvem na cena | `cobertura_valida_pct = 0`; registro gravado como `qualidade=insuficiente`, sem valores de mediana/percentil (`null`). |
| Cena cobre só parte do polígono da área | `cobertura_valida_pct` considera apenas os pixels dentro da interseção cena∩área; pixels fora da cena contam como sem observação, não como zero. |
| Colheita ou pastejo recente (queda abrupta legítima) | O pipeline **não** classifica a queda — apenas registra o valor. A distinção entre queda por manejo e anomalia é responsabilidade do motor de diagnóstico (doc 03), que cruza com histórico de uso e sazonalidade. |
| Gap de vários ciclos de revisita (satélite sem passagem útil) | Série exposta mostra o gap explicitamente; nenhum valor é interpolado para preenchê-lo. |
| Duas cenas no mesmo dia com sobreposição parcial na área | Ambas processadas; se cobrirem partes diferentes da área, a cobertura válida do dia é a união; se cobrirem a mesma parte, mantém-se a de maior cobertura válida e a outra fica registrada como redundante (não descartada do histórico de cenas). |

## Lacunas identificadas

- Esta spec não define ainda o valor final de produção dos limiares (90% nuvem de cena, 60%
  cobertura válida, 15 dias de gap) — os valores acima são defaults de implementação inicial e
  devem ser parametrizáveis (tabela de configuração ou variável de ambiente), não constantes
  fixas no código, para permitir ajuste sem deploy de código novo.
- Comparação entre culturas ou estágios produtivos diferentes como equivalentes é
  explicitamente vedada pela spec de produto — não há regra de normalização entre sistemas
  produtivos distintos nesta fase.

## Fora de escopo

- Modelos calibrados que convertam NDVI/EVI em lotação, produção de leite ou rendimento de
  grãos — a spec de produto proíbe essa conversão direta; modelos calibrados são trabalho
  futuro e específico por sistema produtivo.
- Escolha de outra fonte de imagem além de Sentinel-2 L2A.
- Implementação de código nesta entrega (este documento é a spec para a Fase 3; o scaffold
  atual só cria a estrutura de pastas `workers/geo/app/processing/` vazia).
