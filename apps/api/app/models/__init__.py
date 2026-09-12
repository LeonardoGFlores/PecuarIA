"""Importa todos os modelos para que `Base.metadata` os conheca (Alembic autogenerate)."""

from app.models.execucao import ExecucaoProcessamento
from app.models.meteorologia import (
    AvaliacaoRepresentatividade,
    EstacaoMeteorologica,
    ObservacaoMeteorologica,
)
from app.models.oferta import Fornecedor, LogisticaOferta, OfertaRegional
from app.models.perfil import Equipe, PerfilProdutor
from app.models.territorio import (
    AreaProdutiva,
    Fazenda,
    HistoricoUsoArea,
    PontoInfraestrutura,
)
from app.models.vegetacao import CenaSatelite, IndiceVegetacaoArea

__all__ = [
    "AreaProdutiva",
    "AvaliacaoRepresentatividade",
    "CenaSatelite",
    "Equipe",
    "EstacaoMeteorologica",
    "ExecucaoProcessamento",
    "Fazenda",
    "Fornecedor",
    "HistoricoUsoArea",
    "IndiceVegetacaoArea",
    "LogisticaOferta",
    "ObservacaoMeteorologica",
    "OfertaRegional",
    "PerfilProdutor",
    "PontoInfraestrutura",
]
