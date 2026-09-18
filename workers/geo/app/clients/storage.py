"""Client S3-compativel (boto3) para o armazenamento de rasters recortados
(docs/specs/00, componente de storage de objetos). `endpoint_url`
configuravel: aponta para MinIO em producao/dev normal (via
infra/docker-compose.yml) ou para um mock local (`moto`) em teste — mesmo
codigo de producao em ambos os casos, sem divergencia entre ambientes.
"""

from __future__ import annotations

import boto3
from botocore.client import Config

from app.config import get_settings


def novo_client_s3():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint_url,
        aws_access_key_id=settings.storage_access_key_id,
        aws_secret_access_key=settings.storage_secret_access_key,
        region_name=settings.storage_region,
        config=Config(
            s3={"addressing_style": "path" if settings.storage_force_path_style else "virtual"}
        ),
    )


def garantir_bucket(client, bucket: str) -> None:
    """Cria o bucket se ainda nao existir — idempotente, chamada antes de
    qualquer upload (bucket nao e provisionado por infra fora desta sessao
    de dev)."""
    buckets_existentes = {item["Name"] for item in client.list_buckets().get("Buckets", [])}
    if bucket not in buckets_existentes:
        client.create_bucket(Bucket=bucket)


def salvar_objeto(client, bucket: str, chave: str, conteudo: bytes, content_type: str) -> None:
    client.put_object(Bucket=bucket, Key=chave, Body=conteudo, ContentType=content_type)


def ler_objeto(client, bucket: str, chave: str) -> bytes:
    resposta = client.get_object(Bucket=bucket, Key=chave)
    return resposta["Body"].read()
