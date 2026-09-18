from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://pecuaria:pecuaria@localhost:5432/pecuaria"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    celery_broker_url: str = "redis://localhost:6379/0"

    # Limiares de deteccao de lacunas (docs/specs/04) — cadencia de amostragem
    # diferente entre as series (satelite ~5 dias vs. estacao diaria), por
    # isso limiares separados em vez de um unico compartilhado.
    vegetacao_limiar_gap_dias: int = 15
    meteorologia_limiar_gap_dias: int = 7


@lru_cache
def get_settings() -> Settings:
    return Settings()
