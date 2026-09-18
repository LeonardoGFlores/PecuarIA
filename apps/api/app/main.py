from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routes import fontes, health, meteorologia, perfil, territorio, vegetacao

app = FastAPI(
    title="PecuarIA API",
    description="Cadastro territorial, catalogo de fontes, meteorologia, vegetacao, "
    "analise temporal e perfil do produtor/oferta regional.",
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
app.include_router(meteorologia.router)
app.include_router(vegetacao.router)
app.include_router(perfil.router)
