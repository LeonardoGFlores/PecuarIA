"""Manifesto de execucao (docs/specs/00): toda ingestao/processamento grava
um registro rastreavel em `execucao_processamento` — fontes, versao,
parametros e status de cada execucao — para que o usuario veja o que
sustenta cada dado exibido no Diagnostico/Relatorio.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from app import db_enums
from app.db import get_table


class IngestaoParcialError(Exception):
    """Levantada quando uma ingestao processou parte da janela antes de
    falhar (ex.: timeout no meio de um backfill longo). O manifesto grava
    `status=PARCIAL`, nao `FALHA` — houve progresso real, nao uma tentativa
    perdida por completo."""


def abrir_execucao(
    conn: Connection,
    *,
    tipo: str,
    entrada_fontes: list[str],
    parametros: dict,
    versao_pipeline: str,
) -> uuid.UUID:
    """Grava a execucao como EM_ANDAMENTO e commita imediatamente — se a
    task crashar antes de chegar a `fechar_execucao`, ja fica evidencia da
    tentativa em vez de nada."""
    tabela = get_table("execucao_processamento")
    execucao_id = uuid.uuid4()
    conn.execute(
        insert(tabela).values(
            id=execucao_id,
            tipo=tipo,
            entrada_fontes=entrada_fontes,
            parametros=parametros,
            versao_pipeline=versao_pipeline,
            iniciado_em=datetime.now(timezone.utc),
            status=db_enums.STATUS_EXECUCAO_EM_ANDAMENTO,
            saida_referencias=[],
        )
    )
    conn.commit()
    return execucao_id


def fechar_execucao(
    conn: Connection,
    execucao_id: uuid.UUID,
    *,
    status: str,
    saida_referencias: list[str] | None = None,
    erro: str | None = None,
) -> None:
    tabela = get_table("execucao_processamento")
    valores: dict = {"concluido_em": datetime.now(timezone.utc), "status": status}
    if saida_referencias is not None:
        valores["saida_referencias"] = saida_referencias
    if erro is not None:
        # le os parametros ja gravados na abertura para anexar o erro sem sobrescreve-los
        linha = conn.execute(select(tabela.c.parametros).where(tabela.c.id == execucao_id)).first()
        parametros_atuais = dict(linha.parametros or {}) if linha else {}
        parametros_atuais["erro"] = erro
        valores["parametros"] = parametros_atuais
    conn.execute(update(tabela).where(tabela.c.id == execucao_id).values(**valores))
    conn.commit()


@contextmanager
def rastrear_execucao(
    conn: Connection,
    *,
    tipo: str,
    entrada_fontes: list[str],
    parametros: dict,
    versao_pipeline: str,
) -> Iterator[tuple[uuid.UUID, dict]]:
    """Abre um manifesto de execucao e fecha com o status certo ao sair.

    Uso:
        with rastrear_execucao(conn, tipo=..., ...) as (execucao_id, resultado):
            ...
            resultado["saida_referencias"].append("observacao_meteorologica:...")

    - Sem excecao: fecha como SUCESSO.
    - `IngestaoParcialError`: fecha como PARCIAL (progresso parcial e valido,
      nao propaga a excecao — a task Celery e considerada concluida).
    - Qualquer outra excecao: fecha como FALHA e repropaga, para o Celery
      aplicar sua propria politica de retry/alerta.
    """
    execucao_id = abrir_execucao(
        conn, tipo=tipo, entrada_fontes=entrada_fontes, parametros=parametros, versao_pipeline=versao_pipeline
    )
    resultado: dict = {"saida_referencias": []}
    try:
        yield execucao_id, resultado
    except IngestaoParcialError as exc:
        fechar_execucao(
            conn,
            execucao_id,
            status=db_enums.STATUS_EXECUCAO_PARCIAL,
            saida_referencias=resultado["saida_referencias"],
            erro=str(exc),
        )
    except Exception as exc:
        fechar_execucao(conn, execucao_id, status=db_enums.STATUS_EXECUCAO_FALHA, erro=str(exc))
        raise
    else:
        fechar_execucao(
            conn, execucao_id, status=db_enums.STATUS_EXECUCAO_SUCESSO, saida_referencias=resultado["saida_referencias"]
        )
