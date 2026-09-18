"""Acesso ao Postgres via SQLAlchemy Core, com tabelas refletidas.

O worker NAO importa os models ORM de `apps/api` (nao ha dependencia cruzada
entre os dois pacotes). Motivo concreto: `apps/api/pyproject.toml` e
`workers/geo/pyproject.toml` empacotam ambos um modulo top-level chamado
`app` — instalar os dois no mesmo venv colidiria no nome do pacote. A
estrutura das tabelas (colunas, enums, constraints) e gerenciada apenas pela
Alembic da API; aqui so lemos essa estrutura via reflexao.
"""

from functools import lru_cache

from sqlalchemy import MetaData, Table, create_engine
from sqlalchemy.engine import Engine

from app.config import get_settings

_metadata = MetaData()


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True, future=True)


def get_table(nome: str) -> Table:
    """Retorna a tabela `nome`, refletindo sua estrutura real do Postgres.

    `MetaData` cacheia por nome de tabela — reflexoes repetidas da mesma
    tabela no processo do worker nao re-consultam o catalogo do Postgres.
    """
    if nome in _metadata.tables:
        return _metadata.tables[nome]
    return Table(nome, _metadata, autoload_with=get_engine())
