from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime
from ..database import get_db
from ..models.edizione import Edizione, EdizioneDocente, ModalitaErogazione, ModalitaCheckin, ModalitaTeams, StatoEdizione, RuoloDocente
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.user import User
from ..models.corso import Corso
from .deps import require_training_admin, get_current_user

router = APIRouter(prefix="/api/edizioni", tags=["edizioni"])

class EdizioneIn(BaseModel):
    corso_id: str
    modalita: ModalitaErogazione
    data_inizio: Optional[datetime] = None
    data_fine: Optional[datetime] = None
    luogo: Optional[str] = None
    posti_max: Optional[int] = None
    checkin_mode: Optional[ModalitaCheckin] = ModalitaCheckin.discente_validato
    teams_mode: Optional[ModalitaTeams] = None
    video_id: Optional[str] = None
    ente_erogatore: Optional[str] = None
    ore_dichiarate: Optional[int] = None
    note: Optional[str] = None

    @field_validator("video_id", mode="before")
    @classmethod
    def _stringa_vuota_a_none(cls, v):
        # Il form manda "" quando il campo non è applicabile (es. modalità non video):
        # una stringa vuota non è un UUID valido, va trattata come "nessun valore".
        return v or None

def _is_docente(edizione: Edizione, user: User) -> bool:
    return any(str(d.user_id) == str(user.id) for d in edizione.docenti)

def _serialize(e: Edizione, db: Session):
    n_iscritti = db.query(Iscrizione).filter(Iscrizione.edizione_id == e.id).count()
    corso = db.query(Corso).filter(Corso.id == e.corso_id).first()
    return {
        "id": str(e.id), "corso_id": str(e.corso_id), "corso_titolo": corso.titolo if corso else None,
        "modalita": e.modalita, "stato": e.stato,
        "data_inizio": e.data_inizio, "data_fine": e.data_fine, "luogo": e.luogo,
        "posti_max": e.posti_max, "checkin_mode": e.checkin_mode, "teams_mode": e.teams_mode,
        "teams_join_url": e.teams_join_url, "video_id": str(e.video_id) if e.video_id else None,
        "ente_erogatore": e.ente_erogatore,
        "ore_dichiarate": e.ore_dichiarate, "note": e.note,
        "chiusa_at": e.chiusa_at, "n_iscritti": n_iscritti,
        "docenti": [{"user_id": str(d.user_id), "ruolo": d.ruolo} for d in e.docenti],
    }

@router.get("")
def list_edizioni(corso_id: Optional[str] = None, mie_come_docente: bool = False,
                   db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = db.query(Edizione).options(joinedload(Edizione.docenti))
    if corso_id: q = q.filter(Edizione.corso_id == corso_id)
    if mie_come_docente:
        q = q.join(EdizioneDocente, EdizioneDocente.edizione_id == Edizione.id).filter(EdizioneDocente.user_id == user.id)
    return [_serialize(e, db) for e in q.order_by(Edizione.data_inizio.desc().nullslast()).all()]

@router.get("/mie/iscrizioni")
def mie_iscrizioni(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(Iscrizione).filter(Iscrizione.user_id == user.id).all()
    out = []
    for i in rows:
        e = db.query(Edizione).filter(Edizione.id == i.edizione_id).first()
        corso = db.query(Corso).filter(Corso.id == e.corso_id).first() if e else None
        out.append({
            "id": str(i.id), "edizione_id": str(i.edizione_id), "stato": i.stato,
            "completato_at": i.completato_at, "ripeti_entro": i.ripeti_entro,
            "corso_titolo": corso.titolo if corso else None,
            "corso_validita_mesi": corso.validita_mesi if corso else None,
            "edizione_modalita": e.modalita if e else None,
            "edizione_stato": e.stato if e else None,
            "edizione_data_inizio": e.data_inizio if e else None,
        })
    return out

@router.get("/{edizione_id}")
def get_edizione(edizione_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    e = db.query(Edizione).options(joinedload(Edizione.docenti)).filter(Edizione.id == edizione_id).first()
    if not e: raise HTTPException(404)
    return _serialize(e, db)

@router.post("")
def create_edizione(data: EdizioneIn, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    e = Edizione(**data.model_dump(), stato=StatoEdizione.bozza)
    db.add(e); db.commit(); db.refresh(e)
    return _serialize(e, db)

@router.put("/{edizione_id}")
def update_edizione(edizione_id: str, data: EdizioneIn, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    e = db.query(Edizione).options(joinedload(Edizione.docenti)).filter(Edizione.id == edizione_id).first()
    if not e: raise HTTPException(404)
    if e.stato == StatoEdizione.chiusa:
        raise HTTPException(400, "Edizione chiusa: non modificabile")
    for k, v in data.model_dump().items(): setattr(e, k, v)
    db.commit()
    return _serialize(e, db)

@router.post("/{edizione_id}/pianifica")
def pianifica_edizione(edizione_id: str, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    e = db.query(Edizione).filter(Edizione.id == edizione_id).first()
    if not e: raise HTTPException(404)
    e.stato = StatoEdizione.pianificata
    db.commit()
    return {"ok": True}

# --- Docenti ---

class DocenteIn(BaseModel):
    user_id: str
    ruolo: RuoloDocente = RuoloDocente.titolare

@router.post("/{edizione_id}/docenti")
def aggiungi_docente(edizione_id: str, data: DocenteIn, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    e = db.query(Edizione).filter(Edizione.id == edizione_id).first()
    if not e: raise HTTPException(404)
    esiste = db.query(EdizioneDocente).filter(EdizioneDocente.edizione_id == edizione_id, EdizioneDocente.user_id == data.user_id).first()
    if esiste: raise HTTPException(400, "Già docente su questa edizione")
    db.add(EdizioneDocente(edizione_id=edizione_id, user_id=data.user_id, ruolo=data.ruolo))
    db.commit()
    return {"ok": True}

@router.delete("/{edizione_id}/docenti/{user_id}")
def rimuovi_docente(edizione_id: str, user_id: str, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    db.query(EdizioneDocente).filter(EdizioneDocente.edizione_id == edizione_id, EdizioneDocente.user_id == user_id).delete()
    db.commit()
    return {"ok": True}

# --- Iscrizioni ---

@router.get("/{edizione_id}/iscrizioni")
def list_iscrizioni(edizione_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(Iscrizione).options(joinedload(Iscrizione.evidenze)).filter(Iscrizione.edizione_id == edizione_id).all()
    out = []
    for i in rows:
        u = db.query(User).filter(User.id == i.user_id).first()
        out.append({
            "id": str(i.id), "user_id": str(i.user_id),
            "user_full_name": u.full_name if u else None,
            "stato": i.stato,
            "n_evidenze": len(i.evidenze),
        })
    return out

@router.post("/{edizione_id}/iscrizioni")
def iscrivi(edizione_id: str, user_ids: List[str], db: Session = Depends(get_db), user=Depends(require_training_admin)):
    e = db.query(Edizione).filter(Edizione.id == edizione_id).first()
    if not e: raise HTTPException(404)
    creati = []
    for uid in user_ids:
        esiste = db.query(Iscrizione).filter(Iscrizione.edizione_id == edizione_id, Iscrizione.user_id == uid).first()
        if esiste: continue
        db.add(Iscrizione(edizione_id=edizione_id, user_id=uid))
        creati.append(uid)
    db.commit()
    return {"ok": True, "iscritti": creati}
