from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from ..database import get_db
from ..models.organizzazione import Organizzazione
from .deps import require_admin_tecnico, get_current_user

router = APIRouter(prefix="/api/organizzazioni", tags=["organizzazioni"])

class OrgIn(BaseModel):
    ragione_sociale: str
    tipo: Optional[str] = None
    partita_iva: Optional[str] = None
    accreditamento: Optional[str] = None
    referente: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    note: Optional[str] = None

def _serialize(o: Organizzazione):
    return {"id": str(o.id), "ragione_sociale": o.ragione_sociale, "tipo": o.tipo,
            "partita_iva": o.partita_iva, "accreditamento": o.accreditamento,
            "referente": o.referente, "email": o.email, "telefono": o.telefono, "note": o.note}

@router.get("")
def list_organizzazioni(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return [_serialize(o) for o in db.query(Organizzazione).order_by(Organizzazione.ragione_sociale).all()]

@router.post("")
def create_organizzazione(data: OrgIn, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    o = Organizzazione(**data.model_dump())
    db.add(o); db.commit(); db.refresh(o)
    return _serialize(o)

@router.put("/{org_id}")
def update_organizzazione(org_id: str, data: OrgIn, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    o = db.query(Organizzazione).filter(Organizzazione.id == org_id).first()
    if not o: raise HTTPException(404)
    for k, v in data.model_dump().items(): setattr(o, k, v)
    db.commit()
    return _serialize(o)

@router.delete("/{org_id}")
def delete_organizzazione(org_id: str, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    from ..models.user import User
    if db.query(User).filter(User.organizzazione_id == org_id).first():
        raise HTTPException(400, "Ci sono utenti collegati a questa organizzazione")
    o = db.query(Organizzazione).filter(Organizzazione.id == org_id).first()
    if not o: raise HTTPException(404)
    db.delete(o); db.commit()
    return {"ok": True}
