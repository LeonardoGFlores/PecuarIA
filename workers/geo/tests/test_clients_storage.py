"""Testes do client de storage S3-compativel contra um `moto` local
(ThreadedMotoServer, parte de `moto[server]`) — um servidor HTTP real na
mesma maquina, para validar o `endpoint_url` configuravel de ponta a ponta.
O mesmo `novo_client_s3()`/`salvar_objeto`/`ler_objeto` roda contra MinIO
real em producao/dev normal, sem mudanca de codigo.
"""

from __future__ import annotations

import pytest
from moto.server import ThreadedMotoServer

from app.clients import storage
from app.config import get_settings


@pytest.fixture(scope="module")
def moto_server():
    servidor = ThreadedMotoServer(port=0)
    servidor.start()
    host, port = servidor.get_host_and_port()
    yield f"http://{host}:{port}"
    servidor.stop()


@pytest.fixture
def settings_apontando_para_moto(monkeypatch, moto_server):
    monkeypatch.setenv("STORAGE_ENDPOINT_URL", moto_server)
    monkeypatch.setenv("STORAGE_ACCESS_KEY_ID", "teste")
    monkeypatch.setenv("STORAGE_SECRET_ACCESS_KEY", "teste")
    monkeypatch.setenv("STORAGE_BUCKET", "pecuaria-rasters-teste")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


def test_garantir_bucket_e_idempotente(settings_apontando_para_moto):
    client = storage.novo_client_s3()
    bucket = settings_apontando_para_moto.storage_bucket

    storage.garantir_bucket(client, bucket)
    storage.garantir_bucket(client, bucket)  # segunda chamada nao deve falhar

    buckets = {b["Name"] for b in client.list_buckets()["Buckets"]}
    assert bucket in buckets


def test_salvar_e_ler_objeto_roundtrip(settings_apontando_para_moto):
    client = storage.novo_client_s3()
    bucket = settings_apontando_para_moto.storage_bucket
    storage.garantir_bucket(client, bucket)

    chave = "ndvi-evi/fazenda-teste/area-teste/2024-01-01/cena-teste/ndvi-evi-v1/NDVI.tif"
    conteudo = b"conteudo binario fake de um geotiff"

    storage.salvar_objeto(client, bucket, chave, conteudo, content_type="image/tiff")
    lido = storage.ler_objeto(client, bucket, chave)

    assert lido == conteudo
