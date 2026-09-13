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

    sentinel2_stac_base_url: str = "https://earth-search.aws.element84.com/v1"
    sentinel2_colecao: str = "sentinel-2-l2a"
    sentinel2_limiar_nuvem_cena_pct: float = 90.0
    sentinel2_limiar_cobertura_valida_minima_pct: float = 60.0
    sentinel2_limiar_gap_dias: int = 15
    sentinel2_backfill_dias: int = 30

    storage_endpoint_url: str = "http://localhost:9000"
    storage_bucket: str = "pecuaria-rasters"
    storage_access_key_id: str = "pecuaria"
    storage_secret_access_key: str = "pecuaria123"
    storage_region: str = "us-east-1"
    storage_force_path_style: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
