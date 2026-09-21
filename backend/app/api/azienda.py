from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from ..database import get_db
from ..models.azienda import Azienda
from .deps import require_admin_tecnico, get_current_user

router = APIRouter(prefix="/api/azienda", tags=["azienda"])

class AziendaIn(BaseModel):
    ragione_sociale: Optional[str] = None
    partita_iva: Optional[str] = None
    codice_fiscale: Optional[str] = None
    indirizzo: Optional[str] = None
    cap: Optional[str] = None
    citta: Optional[str] = None
    provincia: Optional[str] = None
    nazione: Optional[str] = "IT"
    email: Optional[str] = None
    pec: Optional[str] = None

def _get_or_create(db: Session) -> Azienda:
    a = db.query(Azienda).first()
    if not a:
        a = Azienda()
        db.add(a); db.commit(); db.refresh(a)
    return a

def _serialize(a: Azienda):
    return {c.name: getattr(a, c.name) for c in a.__table__.columns}

@router.get("")
def get_azienda(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _serialize(_get_or_create(db))

@router.put("")
def update_azienda(data: AziendaIn, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    a = _get_or_create(db)
    for k, v in data.model_dump().items(): setattr(a, k, v)
    db.commit()
    return _serialize(a)
