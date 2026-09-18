"""Fixtures compartilhadas dos testes de rotas — TestClient + Postgres real.

Pulados automaticamente se DATABASE_URL nao estiver acessivel, mesma
convencao usada em workers/geo/tests/test_analysis_vegetacao_integration.py.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.db import SessionLocal, engine
from app.main import app
from app.models.mixins import StatusEvidencia
from app.models.oferta import Fornecedor, TipoFornecedor
from app.models.territorio import Fazenda


@pytest.fixture
def db_session():
    try:
        conexao = engine.connect()
    except OperationalError:
        pytest.skip("Postgres local nao acessivel via DATABASE_URL")
    conexao.close()

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    return TestClient(app)


@pytest.fixture
def fazenda_teste(db_session):
    fazenda = Fazenda(
        nome="Fazenda Teste Fase 5",
        geom="SRID=4326;POLYGON((-47 -15, -47 -15.01, -46.99 -15.01, -46.99 -15, -47 -15))",
        fonte="teste_automatizado",
        status=StatusEvidencia.DECLARADO,
    )
    db_session.add(fazenda)
    db_session.commit()
    db_session.refresh(fazenda)
    fazenda_id = fazenda.id
    yield fazenda_id
    db_session.delete(fazenda)
    db_session.commit()


@pytest.fixture
def fornecedor_teste(db_session):
    fornecedor = Fornecedor(nome="Fornecedor Teste Fase 5", tipo=TipoFornecedor.INSUMOS, fonte="teste_automatizado")
    db_session.add(fornecedor)
    db_session.commit()
    db_session.refresh(fornecedor)
    fornecedor_id = fornecedor.id
    yield fornecedor_id
    # o teste pode ja ter apagado o fornecedor (ex.: caso de cascade) —
    # so limpa se ainda existir.
    remanescente = db_session.get(Fornecedor, fornecedor_id)
    if remanescente is not None:
        db_session.delete(remanescente)
        db_session.commit()
