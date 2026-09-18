"""Testes de /fontes/fornecedores, /fontes/ofertas e /fontes/*/logistica.
Pulados se DATABASE_URL nao estiver acessivel (ver conftest.py)."""

from __future__ import annotations

import datetime as dt
import uuid

AGORA = dt.datetime.now(dt.timezone.utc)


def _payload_oferta(fornecedor_id: uuid.UUID, **overrides) -> dict:
    payload = {
        "fornecedor_id": str(fornecedor_id),
        "categoria": "boi_gordo",
        "unidade": "cabeca",
        "quantidade_disponivel": 100.0,
        "quantidade_minima": 10.0,
        "preco": 3500.0,
        "data_registro": AGORA.isoformat(),
        "validade_cotacao": None,
        "fonte": "cotacao_fornecedor",
    }
    payload.update(overrides)
    return payload


def test_ciclo_completo_fornecedor(client):
    criado = client.post(
        "/fontes/fornecedores", json={"nome": "Fornecedor CRUD", "tipo": "insumos", "fonte": "declarado_produtor"}
    )
    assert criado.status_code == 201
    fornecedor_id = criado.json()["id"]
    assert criado.json()["fonte"] == "declarado_produtor"

    lido = client.get(f"/fontes/fornecedores/{fornecedor_id}")
    assert lido.status_code == 200

    atualizado = client.put(
        f"/fontes/fornecedores/{fornecedor_id}",
        json={"nome": "Fornecedor CRUD Atualizado", "tipo": "insumos", "fonte": "declarado_produtor"},
    )
    assert atualizado.status_code == 200
    assert atualizado.json()["nome"] == "Fornecedor CRUD Atualizado"

    removido = client.delete(f"/fontes/fornecedores/{fornecedor_id}")
    assert removido.status_code == 204

    apos_delete = client.get(f"/fontes/fornecedores/{fornecedor_id}")
    assert apos_delete.status_code == 404


def test_fornecedor_inexistente_retorna_404(client):
    assert client.get(f"/fontes/fornecedores/{uuid.uuid4()}").status_code == 404


def test_criar_oferta_com_fornecedor_inexistente_retorna_404(client):
    resposta = client.post("/fontes/ofertas", json=_payload_oferta(uuid.uuid4()))
    assert resposta.status_code == 404


def test_quantidade_minima_maior_que_disponivel_retorna_422(client, fornecedor_teste):
    resposta = client.post(
        "/fontes/ofertas",
        json=_payload_oferta(fornecedor_teste, quantidade_disponivel=5.0, quantidade_minima=10.0),
    )
    assert resposta.status_code == 422


def test_ciclo_completo_oferta_e_vencida(client, fornecedor_teste):
    passado = (AGORA - dt.timedelta(days=1)).isoformat()
    futuro = (AGORA + dt.timedelta(days=30)).isoformat()

    vencida = client.post("/fontes/ofertas", json=_payload_oferta(fornecedor_teste, validade_cotacao=passado))
    assert vencida.status_code == 201
    assert vencida.json()["vencida"] is True

    vigente = client.post("/fontes/ofertas", json=_payload_oferta(fornecedor_teste, validade_cotacao=futuro))
    assert vigente.status_code == 201
    assert vigente.json()["vencida"] is False

    sem_validade = client.post("/fontes/ofertas", json=_payload_oferta(fornecedor_teste, validade_cotacao=None))
    assert sem_validade.status_code == 201
    assert sem_validade.json()["vencida"] is False

    oferta_id = vigente.json()["id"]
    lida = client.get(f"/fontes/ofertas/{oferta_id}")
    assert lida.status_code == 200

    listada = client.get("/fontes/ofertas", params={"fornecedor_id": str(fornecedor_teste)})
    assert listada.status_code == 200
    assert len(listada.json()) == 3

    atualizada = client.put(
        f"/fontes/ofertas/{oferta_id}", json=_payload_oferta(fornecedor_teste, preco=4000.0, validade_cotacao=futuro)
    )
    assert atualizada.status_code == 200
    assert atualizada.json()["preco"] == 4000.0

    for oferta in (vencida, vigente, sem_validade):
        client.delete(f"/fontes/ofertas/{oferta.json()['id']}")


def test_oferta_inexistente_retorna_404(client):
    assert client.get(f"/fontes/ofertas/{uuid.uuid4()}").status_code == 404


def test_ciclo_completo_logistica(client, fornecedor_teste):
    oferta = client.post("/fontes/ofertas", json=_payload_oferta(fornecedor_teste))
    oferta_id = oferta.json()["id"]

    criada = client.post(
        f"/fontes/ofertas/{oferta_id}/logistica",
        json={"distancia_km": 45.0, "prazo_entrega_dias": 5, "custo_frete": 800.0},
    )
    assert criada.status_code == 201
    logistica_id = criada.json()["id"]

    listada = client.get(f"/fontes/ofertas/{oferta_id}/logistica")
    assert listada.status_code == 200
    assert len(listada.json()) == 1

    atualizada = client.put(
        f"/fontes/logistica/{logistica_id}",
        json={"distancia_km": 45.0, "prazo_entrega_dias": 3, "custo_frete": 900.0},
    )
    assert atualizada.status_code == 200
    assert atualizada.json()["custo_frete"] == 900.0

    removida = client.delete(f"/fontes/logistica/{logistica_id}")
    assert removida.status_code == 204

    client.delete(f"/fontes/ofertas/{oferta_id}")


def test_logistica_para_oferta_inexistente_retorna_404(client):
    resposta = client.post(
        f"/fontes/ofertas/{uuid.uuid4()}/logistica",
        json={"distancia_km": 10.0, "prazo_entrega_dias": 1, "custo_frete": 50.0},
    )
    assert resposta.status_code == 404


def test_custo_frete_negativo_retorna_422(client, fornecedor_teste):
    oferta = client.post("/fontes/ofertas", json=_payload_oferta(fornecedor_teste))
    oferta_id = oferta.json()["id"]
    resposta = client.post(f"/fontes/ofertas/{oferta_id}/logistica", json={"custo_frete": -10.0})
    assert resposta.status_code == 422
    client.delete(f"/fontes/ofertas/{oferta_id}")


def test_deletar_fornecedor_cascateia_oferta_e_logistica(client, db_session):
    from app.models.oferta import Fornecedor, TipoFornecedor

    fornecedor = Fornecedor(nome="Fornecedor Cascade", tipo=TipoFornecedor.ANIMAIS, fonte="teste_automatizado")
    db_session.add(fornecedor)
    db_session.commit()
    db_session.refresh(fornecedor)

    oferta = client.post("/fontes/ofertas", json=_payload_oferta(fornecedor.id))
    oferta_id = oferta.json()["id"]
    logistica = client.post(
        f"/fontes/ofertas/{oferta_id}/logistica",
        json={"distancia_km": 10.0, "prazo_entrega_dias": 1, "custo_frete": 50.0},
    )
    logistica_id = logistica.json()["id"]

    removido = client.delete(f"/fontes/fornecedores/{fornecedor.id}")
    assert removido.status_code == 204

    assert client.get(f"/fontes/ofertas/{oferta_id}").status_code == 404
    assert client.get(f"/fontes/logistica/{logistica_id}").status_code == 404
