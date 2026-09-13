from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    database_url: str = "postgresql+psycopg://pecuaria:pecuaria@localhost:5432/pecuaria"

    inmet_base_url: str = "https://apitempo.inmet.gov.br"
    nasa_power_base_url: str = "https://power.larc.nasa.gov/api/temporal/daily/point"
    http_timeout_segundos: float = 30.0

    inmet_backfill_anos: int = 2
    nasa_power_backfill_anos: int = 5
    raio_representatividade_km: float = 100.0
    janela_representatividade_dias: int = 365


@lru_cache
def get_settings() -> Settings:
    return Settings()
