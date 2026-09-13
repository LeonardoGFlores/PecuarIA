"""Celery app do worker de processamento geoespacial.

`celery_app` e definido primeiro; os modulos de tasks (ingestion/*, quality/*)
sao importados so no final deste arquivo, depois que `celery_app` ja existe
no namespace do modulo — eles importam `from app.tasks import celery_app`
para se registrar via decorator, e essa ordem evita import circular.
"""

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "pecuaria_geo",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"])

celery_app.conf.task_routes = {
    "clima.inmet.*": {"queue": "clima_inmet"},
    "clima.nasa_power.*": {"queue": "clima_nasa_power"},
    "qualidade.*": {"queue": "qualidade"},
    "satelite.descobrir_cenas": {"queue": "satelite_descoberta"},
    "satelite.despachar_descoberta": {"queue": "satelite_descoberta"},
    "satelite.processar_cena_area": {"queue": "satelite_processamento"},
    "satelite.despachar_processamento_pendente": {"queue": "satelite_processamento"},
}

celery_app.conf.beat_schedule = {
    "clima-inmet-sincronizar-catalogo": {
        "task": "clima.inmet.sincronizar_catalogo",
        "schedule": crontab(day_of_month=1, hour=3, minute=0),
    },
    "clima-inmet-despachar-incrementais": {
        "task": "clima.inmet.despachar_incrementais",
        "schedule": crontab(hour=6, minute=0),
    },
    "clima-nasa-power-despachar-refresh": {
        "task": "clima.nasa_power.despachar_refresh",
        "schedule": crontab(day_of_week=1, hour=5, minute=0),
    },
    "qualidade-despachar-avaliacoes": {
        "task": "qualidade.despachar_avaliacoes",
        "schedule": crontab(day_of_week=0, hour=4, minute=0),
    },
    "satelite-despachar-descoberta": {
        "task": "satelite.despachar_descoberta",
        "schedule": crontab(hour=7, minute=0),
    },
    "satelite-despachar-processamento-pendente": {
        "task": "satelite.despachar_processamento_pendente",
        "schedule": crontab(minute=0, hour="*/6"),
    },
}


@celery_app.task(name="geo.health_check")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


# Import no final: registra as tasks de cada modulo via @celery_app.task,
# usando o `celery_app` ja definido acima. nasa_power precisa ser importado
# ANTES de quality.representatividade: esse modulo aciona o fallback NASA
# POWER e importa `app.ingestion.nasa_power` — se essa ordem for invertida,
# vira import circular (nasa_power tambem precisa de `celery_app` daqui).
from app.ingestion import inmet as _inmet_tasks  # noqa: E402,F401
from app.ingestion import nasa_power as _nasa_power_tasks  # noqa: E402,F401
from app.ingestion import sentinel2 as _sentinel2_tasks  # noqa: E402,F401
from app.quality import representatividade as _representatividade_tasks  # noqa: E402,F401
