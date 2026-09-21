from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from ..database import get_db
from ..models.corso import Corso, AzioneTestNonSuperato
from .deps import require_training_admin, get_current_user

router = APIRouter(prefix="/api/corsi", tags=["corsi"])

class CorsoIn(BaseModel):
    titolo: str
    descrizione: Optional[str] = None
    categoria: Optional[str] = None
    validita_mesi: Optional[int] = None
    ha_test_finale: bool = False
    azione_test_non_superato: AzioneTestNonSuperato = AzioneTestNonSuperato.concludi_comunque
    giorni_scadenza_breve: Optional[int] = None
    is_active: bool = True

def _serialize(c: Corso):
    return {"id": str(c.id), "titolo": c.titolo, "descrizione": c.descrizione,
            "categoria": c.categoria, "validita_mesi": c.validita_mesi,
            "ha_test_finale": c.ha_test_finale,
            "azione_test_non_superato": c.azione_test_non_superato,
            "giorni_scadenza_breve": c.giorni_scadenza_breve,
            "is_active": c.is_active, "created_at": c.created_at}

@router.get("")
def list_corsi(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return [_serialize(c) for c in db.query(Corso).order_by(Corso.titolo).all()]

@router.get("/{corso_id}")
def get_corso(corso_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = db.query(Corso).filter(Corso.id == corso_id).first()
    if not c: raise HTTPException(404)
    return _serialize(c)

@router.post("")
def create_corso(data: CorsoIn, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    c = Corso(**data.model_dump())
    db.add(c); db.commit(); db.refresh(c)
    return _serialize(c)

@router.put("/{corso_id}")
def update_corso(corso_id: str, data: CorsoIn, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    c = db.query(Corso).filter(Corso.id == corso_id).first()
    if not c: raise HTTPException(404)
    for k, v in data.model_dump().items(): setattr(c, k, v)
    db.commit()
    return _serialize(c)

@router.delete("/{corso_id}")
def delete_corso(corso_id: str, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    c = db.query(Corso).filter(Corso.id == corso_id).first()
    if not c: raise HTTPException(404)
    c.is_active = False
    db.commit()
    return {"ok": True}
