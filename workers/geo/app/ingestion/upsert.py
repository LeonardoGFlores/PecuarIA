"""Upsert idempotente de observacoes meteorologicas.

`ON CONFLICT (estacao_id, variavel, timestamp) DO UPDATE` — condicionado a
`valor IS DISTINCT FROM EXCLUDED.valor` para nao gerar um UPDATE sem efeito
a cada reprocessamento de uma janela com overlap (backfill/incremental).
"""

from __future__ import annotations

import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from app.db import get_table


def upsert_observacoes(conn: Connection, linhas: list[dict]) -> int:
    """Insere/atualiza linhas de `observacao_meteorologica`.

    Cada linha precisa de: estacao_id, variavel, timestamp, valor, unidade,
    status, versao_processamento (flag_qualidade e opcional). `id` e gerado
    aqui se ausente — tabelas refletidas via Core nao herdam o
    `default=uuid.uuid4` do model ORM da API (so defaults do lado do banco).

    Retorna quantas linhas foram efetivamente inseridas ou atualizadas (nao
    conta os no-ops filtrados pelo WHERE do ON CONFLICT).
    """
    if not linhas:
        return 0

    tabela = get_table("observacao_meteorologica")
    linhas_com_id = [{"id": linha.get("id") or uuid.uuid4(), **linha} for linha in linhas]

    stmt = pg_insert(tabela).values(linhas_com_id)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_observacao_estacao_variavel_timestamp",
        set_={
            "valor": stmt.excluded.valor,
            "unidade": stmt.excluded.unidade,
            "flag_qualidade": stmt.excluded.flag_qualidade,
            "status": stmt.excluded.status,
            "versao_processamento": stmt.excluded.versao_processamento,
        },
        where=tabela.c.valor.is_distinct_from(stmt.excluded.valor),
    ).returning(tabela.c.id)
    # cursor.rowcount nao e confiavel aqui (o driver reporta -1 para o modo
    # de insercao em lote que o SQLAlchemy usa para INSERT com VALUES em
    # lista) — RETURNING da a contagem real: Postgres so retorna a linha
    # quando ela e de fato inserida OU quando o WHERE do DO UPDATE permite a
    # atualizacao, exatamente as linhas "efetivamente afetadas".
    resultado = conn.execute(stmt)
    linhas_afetadas = len(resultado.fetchall())
    conn.commit()
    return linhas_afetadas
