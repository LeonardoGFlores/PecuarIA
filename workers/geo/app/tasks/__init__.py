"""Celery app do worker de processamento geoespacial.

Fase 1: so existe uma task de exemplo para validar que a fila (Redis + Celery)
esta operacional. As tasks reais de ingestao/NDVI/EVI (docs/specs/02) e
diagnostico (docs/specs/03) sao adicionadas nas Fases 2, 3 e 6.
"""

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "pecuaria_geo",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"])


@celery_app.task(name="geo.health_check")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
