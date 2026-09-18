import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.perfil import Equipe, PerfilProdutor
from app.models.territorio import Fazenda
from app.schemas.perfil import EquipeCreate, EquipeRead, PerfilProdutorCreate, PerfilProdutorRead

router = APIRouter(prefix="/fazendas/{fazenda_id}", tags=["perfil-do-produtor"])


def _get_fazenda_ou_404(db: Session, fazenda_id: uuid.UUID) -> None:
    if db.get(Fazenda, fazenda_id) is None:
        raise HTTPException(status_code=404, detail="Fazenda nao encontrada")


@router.get("/perfil-produtor", response_model=PerfilProdutorRead)
def obter_perfil_produtor(fazenda_id: uuid.UUID, db: Session = Depends(get_db)) -> PerfilProdutorRead:
    _get_fazenda_ou_404(db, fazenda_id)
    perfil = db.execute(select(PerfilProdutor).where(PerfilProdutor.fazenda_id == fazenda_id)).scalar_one_or_none()
    if perfil is None:
        raise HTTPException(status_code=404, detail="Perfil do produtor ainda nao cadastrado para esta fazenda")
    return PerfilProdutorRead.model_validate(perfil, from_attributes=True)


@router.post("/perfil-produtor", response_model=PerfilProdutorRead, status_code=201)
def criar_perfil_produtor(
    fazenda_id: uuid.UUID, payload: PerfilProdutorCreate, db: Session = Depends(get_db)
) -> PerfilProdutorRead:
    _get_fazenda_ou_404(db, fazenda_id)
    existente = db.execute(select(PerfilProdutor).where(PerfilProdutor.fazenda_id == fazenda_id)).scalar_one_or_none()
    if existente is not None:
        raise HTTPException(status_code=409, detail="Perfil do produtor ja cadastrado para esta fazenda; use PUT")

    perfil = PerfilProdutor(fazenda_id=fazenda_id, **payload.model_dump())
    db.add(perfil)
    db.commit()
    db.refresh(perfil)
    return PerfilProdutorRead.model_validate(perfil, from_attributes=True)


@router.put("/perfil-produtor", response_model=PerfilProdutorRead)
def atualizar_perfil_produtor(
    fazenda_id: uuid.UUID, payload: PerfilProdutorCreate, db: Session = Depends(get_db)
) -> PerfilProdutorRead:
    _get_fazenda_ou_404(db, fazenda_id)
    perfil = db.execute(select(PerfilProdutor).where(PerfilProdutor.fazenda_id == fazenda_id)).scalar_one_or_none()
    if perfil is None:
        raise HTTPException(status_code=404, detail="Perfil do produtor ainda nao cadastrado para esta fazenda")

    for campo, valor in payload.model_dump().items():
        setattr(perfil, campo, valor)
    db.commit()
    db.refresh(perfil)
    return PerfilProdutorRead.model_validate(perfil, from_attributes=True)


@router.delete("/perfil-produtor", status_code=204)
def remover_perfil_produtor(fazenda_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    _get_fazenda_ou_404(db, fazenda_id)
    perfil = db.execute(select(PerfilProdutor).where(PerfilProdutor.fazenda_id == fazenda_id)).scalar_one_or_none()
    if perfil is None:
        raise HTTPException(status_code=404, detail="Perfil do produtor ainda nao cadastrado para esta fazenda")
    db.delete(perfil)
    db.commit()


@router.get("/equipe", response_model=EquipeRead)
def obter_equipe(fazenda_id: uuid.UUID, db: Session = Depends(get_db)) -> EquipeRead:
    _get_fazenda_ou_404(db, fazenda_id)
    equipe = db.execute(select(Equipe).where(Equipe.fazenda_id == fazenda_id)).scalar_one_or_none()
    if equipe is None:
        raise HTTPException(status_code=404, detail="Equipe ainda nao cadastrada para esta fazenda")
    return EquipeRead.model_validate(equipe, from_attributes=True)


@router.post("/equipe", response_model=EquipeRead, status_code=201)
def criar_equipe(fazenda_id: uuid.UUID, payload: EquipeCreate, db: Session = Depends(get_db)) -> EquipeRead:
    _get_fazenda_ou_404(db, fazenda_id)
    existente = db.execute(select(Equipe).where(Equipe.fazenda_id == fazenda_id)).scalar_one_or_none()
    if existente is not None:
        raise HTTPException(status_code=409, detail="Equipe ja cadastrada para esta fazenda; use PUT")

    equipe = Equipe(fazenda_id=fazenda_id, **payload.model_dump())
    db.add(equipe)
    db.commit()
    db.refresh(equipe)
    return EquipeRead.model_validate(equipe, from_attributes=True)


@router.put("/equipe", response_model=EquipeRead)
def atualizar_equipe(fazenda_id: uuid.UUID, payload: EquipeCreate, db: Session = Depends(get_db)) -> EquipeRead:
    _get_fazenda_ou_404(db, fazenda_id)
    equipe = db.execute(select(Equipe).where(Equipe.fazenda_id == fazenda_id)).scalar_one_or_none()
    if equipe is None:
        raise HTTPException(status_code=404, detail="Equipe ainda nao cadastrada para esta fazenda")

    for campo, valor in payload.model_dump().items():
        setattr(equipe, campo, valor)
    db.commit()
    db.refresh(equipe)
    return EquipeRead.model_validate(equipe, from_attributes=True)


@router.delete("/equipe", status_code=204)
def remover_equipe(fazenda_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    _get_fazenda_ou_404(db, fazenda_id)
    equipe = db.execute(select(Equipe).where(Equipe.fazenda_id == fazenda_id)).scalar_one_or_none()
    if equipe is None:
        raise HTTPException(status_code=404, detail="Equipe ainda nao cadastrada para esta fazenda")
    db.delete(equipe)
    db.commit()
