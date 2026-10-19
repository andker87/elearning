from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from ..database import get_db
from ..models.mansione import Mansione, UserMansione
from ..models.percorso import PercorsoFormativo
from ..services import audit as audit_svc
from .deps import require_admin_tecnico, get_current_user

router = APIRouter(prefix="/api/mansioni", tags=["mansioni"])


class MansioneIn(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#5a6b8a"


class MansioneUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None


def _serialize(m: Mansione, persone: int = 0):
    return {"id": str(m.id), "name": m.name, "description": m.description, "color": m.color,
            "is_active": m.is_active, "persone": persone}


def _nome_libero(db: Session, nome: str, escludi_id=None) -> bool:
    q = db.query(Mansione.id).filter(func.lower(Mansione.name) == nome.strip().lower())
    if escludi_id:
        q = q.filter(Mansione.id != escludi_id)
    return q.first() is None


@router.get("")
def elenco(db: Session = Depends(get_db), user=Depends(get_current_user)):
    conteggi = dict(db.query(UserMansione.mansione_id, func.count(UserMansione.id)).group_by(UserMansione.mansione_id).all())
    return [_serialize(m, conteggi.get(m.id, 0)) for m in sorted(db.query(Mansione).all(), key=lambda m: m.name.casefold())]


@router.post("")
def crea(data: MansioneIn, request: Request, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    nome = data.name.strip()
    if not nome:
        raise HTTPException(400, "Il nome è obbligatorio")
    if not _nome_libero(db, nome):
        raise HTTPException(400, "Esiste già una mansione con questo nome")
    m = Mansione(name=nome, description=data.description, color=data.color)
    try:
        with db.begin_nested():
            db.add(m); db.flush()
    except IntegrityError:
        raise HTTPException(400, "Esiste già una mansione con questo nome")
    audit_svc.log_from_request(db, request, user, "CREATE", entity_type="mansione", entity_id=str(m.id), entity_name=m.name)
    db.commit(); db.refresh(m)
    return _serialize(m)


@router.put("/{mansione_id}")
def modifica(mansione_id: str, data: MansioneUpdate, request: Request, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    m = db.query(Mansione).filter(Mansione.id == mansione_id).first()
    if not m:
        raise HTTPException(404)
    if data.name is not None:
        nome = data.name.strip()
        if not nome:
            raise HTTPException(400, "Il nome è obbligatorio")
        if not _nome_libero(db, nome, m.id):
            raise HTTPException(400, "Esiste già una mansione con questo nome")
        m.name = nome
    for campo in ("description", "color", "is_active"):
        val = getattr(data, campo)
        if val is not None:
            setattr(m, campo, val)
    audit_svc.log_from_request(db, request, user, "UPDATE", entity_type="mansione", entity_id=str(m.id), entity_name=m.name)
    db.commit()
    return _serialize(m)


@router.delete("/{mansione_id}")
def elimina(mansione_id: str, request: Request, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    m = db.query(Mansione).filter(Mansione.id == mansione_id).first()
    if not m:
        raise HTTPException(404)
    if db.query(PercorsoFormativo.id).filter(PercorsoFormativo.trigger_mansione_id == m.id).first():
        raise HTTPException(400, "Un percorso si assegna ancora automaticamente a questa mansione: cambia prima il suo trigger")
    db.query(UserMansione).filter(UserMansione.mansione_id == m.id).delete()
    audit_svc.log_from_request(db, request, user, "DELETE", entity_type="mansione", entity_id=str(m.id), entity_name=m.name)
    db.delete(m); db.commit()
    return {"ok": True}
