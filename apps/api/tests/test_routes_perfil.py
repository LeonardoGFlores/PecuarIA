"""Testes de /fazendas/{id}/perfil-produtor e /fazendas/{id}/equipe — CRUD
singleton por fazenda. Pulados se DATABASE_URL nao estiver acessivel (ver
conftest.py)."""

from __future__ import annotations

import uuid


def test_perfil_produtor_nao_cadastrado_retorna_404(client, fazenda_teste):
    resposta = client.get(f"/fazendas/{fazenda_teste}/perfil-produtor")
    assert resposta.status_code == 404


def test_fazenda_inexistente_retorna_404(client):
    resposta = client.get(f"/fazendas/{uuid.uuid4()}/perfil-produtor")
    assert resposta.status_code == 404


def test_ciclo_completo_perfil_produtor(client, fazenda_teste):
    payload = {
        "objetivos": ["renda", "expansao"],
        "capital_disponivel": 50000.0,
        "tolerancia_risco": "media",
        "disponibilidade_gestao_horas_semana": 20.0,
    }
    criado = client.post(f"/fazendas/{fazenda_teste}/perfil-produtor", json=payload)
    assert criado.status_code == 201
    assert criado.json()["capital_disponivel"] == 50000.0

    segundo_post = client.post(f"/fazendas/{fazenda_teste}/perfil-produtor", json=payload)
    assert segundo_post.status_code == 409

    lido = client.get(f"/fazendas/{fazenda_teste}/perfil-produtor")
    assert lido.status_code == 200
    assert lido.json()["objetivos"] == ["renda", "expansao"]

    atualizado = client.put(
        f"/fazendas/{fazenda_teste}/perfil-produtor", json={**payload, "capital_disponivel": 75000.0}
    )
    assert atualizado.status_code == 200
    assert atualizado.json()["capital_disponivel"] == 75000.0

    removido = client.delete(f"/fazendas/{fazenda_teste}/perfil-produtor")
    assert removido.status_code == 204

    apos_delete = client.get(f"/fazendas/{fazenda_teste}/perfil-produtor")
    assert apos_delete.status_code == 404


def test_disponibilidade_gestao_horas_semana_acima_de_168_retorna_422(client, fazenda_teste):
    resposta = client.post(
        f"/fazendas/{fazenda_teste}/perfil-produtor",
        json={"disponibilidade_gestao_horas_semana": 200.0},
    )
    assert resposta.status_code == 422


def test_capital_disponivel_negativo_retorna_422(client, fazenda_teste):
    resposta = client.post(
        f"/fazendas/{fazenda_teste}/perfil-produtor",
        json={"capital_disponivel": -10.0},
    )
    assert resposta.status_code == 422


def test_equipe_nao_cadastrada_retorna_404(client, fazenda_teste):
    resposta = client.get(f"/fazendas/{fazenda_teste}/equipe")
    assert resposta.status_code == 404


def test_ciclo_completo_equipe(client, fazenda_teste):
    payload = {
        "quantidade_pessoas": 3,
        "funcoes": ["vaqueiro", "gerente"],
        "apoio_tecnico": "proprio",
    }
    criado = client.post(f"/fazendas/{fazenda_teste}/equipe", json=payload)
    assert criado.status_code == 201
    assert criado.json()["quantidade_pessoas"] == 3

    segundo_post = client.post(f"/fazendas/{fazenda_teste}/equipe", json=payload)
    assert segundo_post.status_code == 409

    atualizado = client.put(f"/fazendas/{fazenda_teste}/equipe", json={**payload, "quantidade_pessoas": 5})
    assert atualizado.status_code == 200
    assert atualizado.json()["quantidade_pessoas"] == 5

    removido = client.delete(f"/fazendas/{fazenda_teste}/equipe")
    assert removido.status_code == 204

    apos_delete = client.get(f"/fazendas/{fazenda_teste}/equipe")
    assert apos_delete.status_code == 404


def test_quantidade_pessoas_negativa_retorna_422(client, fazenda_teste):
    resposta = client.post(f"/fazendas/{fazenda_teste}/equipe", json={"quantidade_pessoas": -1})
    assert resposta.status_code == 422
