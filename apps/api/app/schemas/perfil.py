import uuid

from pydantic import BaseModel, Field

from app.models.perfil import ApoioTecnico, ToleranciaRisco


class PerfilProdutorCreate(BaseModel):
    objetivos: list[str] = []
    capital_disponivel: float | None = Field(default=None, ge=0)
    limite_investimento: float | None = Field(default=None, ge=0)
    capital_giro: float | None = Field(default=None, ge=0)
    tolerancia_risco: ToleranciaRisco = ToleranciaRisco.MEDIA
    disponibilidade_gestao_horas_semana: float | None = Field(default=None, ge=0, le=168)


class PerfilProdutorRead(BaseModel):
    id: uuid.UUID
    fazenda_id: uuid.UUID
    objetivos: list[str]
    capital_disponivel: float | None
    limite_investimento: float | None
    capital_giro: float | None
    tolerancia_risco: ToleranciaRisco
    disponibilidade_gestao_horas_semana: float | None


class EquipeCreate(BaseModel):
    quantidade_pessoas: int = Field(default=0, ge=0)
    funcoes: list[str] = []
    disponibilidade_sazonal: dict | None = None
    competencias: list[str] = []
    apoio_tecnico: ApoioTecnico = ApoioTecnico.NENHUM


class EquipeRead(BaseModel):
    id: uuid.UUID
    fazenda_id: uuid.UUID
    quantidade_pessoas: int
    funcoes: list[str]
    disponibilidade_sazonal: dict | None
    competencias: list[str]
    apoio_tecnico: ApoioTecnico
