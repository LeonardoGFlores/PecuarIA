"""Cliente Celery "produtor" enxuto para a API enfileirar tasks do worker
(`workers/geo`) sem importar codigo do worker.

A API e o worker sao pacotes Python separados (ambos definem um modulo
top-level `app` — ver docstring de `workers/geo/app/db.py` para o motivo de
nao compartilhar codigo entre eles). Enfileirar por nome de task (string),
com um `Celery` conectado so ao broker, evita essa colisao: nao e preciso
conhecer a implementacao da task, so seu nome registrado.
"""

from celery import Celery

from app.core.config import get_settings

producer = Celery(broker=get_settings().celery_broker_url)


def enfileirar(nome_task: str, *args: object) -> None:
    producer.send_task(nome_task, args=args)
