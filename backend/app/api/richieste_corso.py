from fastapi import APIRouter, Depends, HTTPException, Request
from ..services import audit as audit_svc
from uuid import UUID
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
from ..database import get_db
from ..models.richiesta_corso import RichiestaCorso, RichiestaCorsoPersona, StatoRichiestaCorso
from ..models.corso import Corso
from ..models.user import User
from ..services.gerarchia import e_responsabile, sottoposti_di
from .deps import get_current_user, require_training_admin

router = APIRouter(prefix="/api/richieste-corso", tags=["richieste-corso"])

class RichiestaCorsoIn(BaseModel):
    corso_id: Optional[str] = None
    argomento: Optional[str] = None
    note: Optional[str] = None
    persone_ids: List[str] = []

class RichiestaCorsoValuta(BaseModel):
    stato: StatoRichiestaCorso
    nota_valutazione: Optional[str] = None

def _is_admin(user: User) -> bool:
    return user.ha_poteri_formazione

def _uuid(valore: str, cosa: str) -> str:
    try:
        return str(UUID(str(valore)))
    except ValueError:
        raise HTTPException(400, f"{cosa} non valido")

def _serialize(r: RichiestaCorso, db: Session, richiedenti: Optional[dict] = None, corsi: Optional[dict] = None):
    """Con i dizionari richiedenti/corsi (elenco) non si fa una query per riga."""
    richiedente = richiedenti[r.richiedente_id] if richiedenti is not None and r.richiedente_id in richiedenti else (
        db.query(User).filter(User.id == r.richiedente_id).first() if richiedenti is None else None)
    corso = (corsi.get(r.corso_id) if corsi is not None else db.query(Corso).filter(Corso.id == r.corso_id).first()) if r.corso_id else None
    return {
        "id": str(r.id),
        "richiedente_id": str(r.richiedente_id), "richiedente_nome": richiedente.full_name if richiedente else None,
        "corso_id": str(r.corso_id) if r.corso_id else None, "corso_titolo": corso.titolo if corso else None,
        "argomento": r.argomento, "note": r.note, "stato": r.stato,
        "nota_valutazione": r.nota_valutazione,
        "n_persone": len(r.persone),
        "persone": [{"id": str(p.user_id), "full_name": p.utente.full_name if p.utente else None} for p in r.persone],
        "created_at": r.created_at, "valutata_at": r.valutata_at,
    }

@router.post("")
def crea_richiesta(data: RichiestaCorsoIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not _is_admin(user) and not e_responsabile(db, user.id):
        raise HTTPException(403, "Solo un responsabile può richiedere un corso")
    argomento = (data.argomento or "").strip() or None
    if not data.corso_id and not argomento:
        raise HTTPException(400, "Indica un corso a catalogo o un argomento")
    corso_id = _uuid(data.corso_id, "Corso") if data.corso_id else None
    if corso_id and not db.query(Corso).filter(Corso.id == corso_id).first():
        raise HTTPException(404, "Corso non trovato")
    persone_ids = list(dict.fromkeys(_uuid(uid, "Identificativo della persona") for uid in data.persone_ids))
    if persone_ids:
        if db.query(User).filter(User.id.in_(persone_ids)).count() != len(persone_ids):
            raise HTTPException(404, "Una o più persone non esistono")
        if not _is_admin(user):
            sottoposti_ids = {str(s.id) for s in sottoposti_di(db, user.id)}
            non_autorizzati = [uid for uid in persone_ids if uid not in sottoposti_ids]
            if non_autorizzati:
                raise HTTPException(403, "Puoi pre-iscrivere solo le persone sotto la tua responsabilità")

    r = RichiestaCorso(richiedente_id=user.id, corso_id=corso_id,
                        argomento=argomento, note=data.note)
    db.add(r); db.flush()
    for uid in persone_ids:
        db.add(RichiestaCorsoPersona(richiesta_id=r.id, user_id=uid))
    corso_rich = db.query(Corso).filter(Corso.id == corso_id).first() if corso_id else None
    audit_svc.log_from_request(db, request, user, "CREATE", entity_type="richiesta_corso", entity_id=str(r.id),
                                entity_name=corso_rich.titolo if corso_rich else argomento)
    db.commit(); db.refresh(r)
    return _serialize(r, db)

@router.get("")
def list_richieste(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(RichiestaCorso).options(joinedload(RichiestaCorso.persone).joinedload(RichiestaCorsoPersona.utente))
    if not _is_admin(user):
        q = q.filter(RichiestaCorso.richiedente_id == user.id)
    rows = q.order_by(RichiestaCorso.created_at.desc()).all()
    richiedenti = {u.id: u for u in db.query(User).filter(User.id.in_({r.richiedente_id for r in rows})).all()} if rows else {}
    corsi = {c.id: c for c in db.query(Corso).filter(Corso.id.in_({r.corso_id for r in rows if r.corso_id})).all()} if rows else {}
    return [_serialize(r, db, richiedenti, corsi) for r in rows]

@router.put("/{richiesta_id}/valuta")
def valuta_richiesta(richiesta_id: str, data: RichiestaCorsoValuta, request: Request,
                      db: Session = Depends(get_db), user: User = Depends(require_training_admin)):
    r = db.query(RichiestaCorso).filter(RichiestaCorso.id == richiesta_id).first()
    if not r: raise HTTPException(404)
    if data.stato == StatoRichiestaCorso.in_attesa:
        raise HTTPException(400, "Lo stato di valutazione deve essere approvata o rifiutata")
    if r.stato != StatoRichiestaCorso.in_attesa:
        raise HTTPException(400, "La richiesta è già stata valutata")
    r.stato = data.stato
    r.nota_valutazione = data.nota_valutazione
    r.valutata_da_id = user.id
    r.valutata_at = datetime.now(timezone.utc)
    audit_svc.log_from_request(db, request, user, "EVALUATE", entity_type="richiesta_corso", entity_id=str(r.id),
                                entity_name=r.argomento, detail=f"esito: {data.stato.value}")
    db.commit()
    return _serialize(r, db)
