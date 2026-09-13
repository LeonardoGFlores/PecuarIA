"""Espelha os labels reais dos tipos enum do Postgres, gerenciados pela
Alembic da API (`apps/api/app/models/*.py`).

O worker nao importa os enums Python da API (ver docstring de `db.py` — os
dois pacotes empacotam um modulo top-level `app`, colidindo se instalados
juntos). Como SQLAlchemy usa o NOME do membro do enum Python (maiusculo)
como label da coluna Postgres — nao o `.value` minusculo usado no restante
do dominio — estas constantes reproduzem esses labels para uso em
INSERT/UPDATE via Core. Se um enum da API ganhar ou renomear um membro,
atualize aqui tambem.
"""

FONTE_INMET = "INMET"
FONTE_NASA_POWER = "NASA_POWER"

TIPO_ESTACAO_OBSERVADO = "OBSERVADO"
TIPO_ESTACAO_GRADE = "GRADE"

VARIAVEL_PRECIPITACAO = "PRECIPITACAO"
VARIAVEL_TEMPERATURA = "TEMPERATURA"
VARIAVEL_UMIDADE_RELATIVA = "UMIDADE_RELATIVA"
VARIAVEL_RADIACAO = "RADIACAO"
VARIAVEL_VENTO = "VENTO"

TODAS_VARIAVEIS = [
    VARIAVEL_PRECIPITACAO,
    VARIAVEL_TEMPERATURA,
    VARIAVEL_UMIDADE_RELATIVA,
    VARIAVEL_RADIACAO,
    VARIAVEL_VENTO,
]

STATUS_OBSERVADO = "OBSERVADO"
STATUS_ESTIMADO = "ESTIMADO"

PAPEL_REFERENCIA = "REFERENCIA"
PAPEL_AUXILIAR = "AUXILIAR"

NIVEL_BOM = "BOM"
NIVEL_REGULAR = "REGULAR"
NIVEL_INSUFICIENTE = "INSUFICIENTE"

TIPO_EXECUCAO_INGESTAO_CLIMA = "INGESTAO_CLIMA"
TIPO_EXECUCAO_AVALIACAO_REPRESENTATIVIDADE = "AVALIACAO_REPRESENTATIVIDADE"

STATUS_EXECUCAO_SUCESSO = "SUCESSO"
STATUS_EXECUCAO_FALHA = "FALHA"
STATUS_EXECUCAO_PARCIAL = "PARCIAL"
STATUS_EXECUCAO_EM_ANDAMENTO = "EM_ANDAMENTO"
