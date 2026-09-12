from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routes import fontes, health, territorio

app = FastAPI(
    title="PecuarIA API",
    description="Cadastro territorial e catalogo de fontes (Fase 1 do roadmap).",
    version="0.1.0",
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(territorio.router)
app.include_router(fontes.router)
