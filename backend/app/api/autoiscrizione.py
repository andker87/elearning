from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from ..database import get_db
from ..models.autoiscrizione import AutoIscrizioneRichiesta, StatoAutoIscrizione
from ..models.edizione import Edizione
from ..models.corso import Corso
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.user import User
from ..services.gerarchia import responsabili_di, sottoposti_di
from ..services.iscrizioni import crea_iscrizione_con_capacita
from ..services.notifiche import invia_invito_calendario
from ..services import audit as audit_svc
from .deps import get_current_user

router = APIRouter(prefix="/api/autoiscrizioni", tags=["autoiscrizioni"])

def _serialize(r: AutoIscrizioneRichiesta, db: Session):
    u = db.query(User).filter(User.id == r.user_id).first()
    e = db.query(Edizione).filter(Edizione.id == r.edizione_id).first()
    corso = db.query(Corso).filter(Corso.id == e.corso_id).first() if e else None
    return {
        "id": str(r.id), "edizione_id": str(r.edizione_id), "corso_titolo": corso.titolo if corso else None,
        "user_id": str(r.user_id), "user_nome": u.full_name if u else None,
        "stato": r.stato, "created_at": r.created_at,
    }

@router.post("/edizioni/{edizione_id}")
def richiedi_autoiscrizione(edizione_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    e = db.query(Edizione).filter(Edizione.id == edizione_id).first()
    if not e: raise HTTPException(404)
    corso = db.query(Corso).filter(Corso.id == e.corso_id).first()
    if not corso or not corso.permetti_autoiscrizione:
        raise HTTPException(403, "Questo corso non permette l'auto-iscrizione")
    gia = db.query(Iscrizione).filter(Iscrizione.edizione_id == edizione_id, Iscrizione.user_id == user.id,
                                       Iscrizione.stato != StatoIscrizione.annullato).first()
    if gia: raise HTTPException(400, "Sei già iscritto a questa sessione")
    gia_richiesta = db.query(AutoIscrizioneRichiesta).filter(AutoIscrizioneRichiesta.edizione_id == edizione_id,
                             AutoIscrizioneRichiesta.user_id == user.id, AutoIscrizioneRichiesta.stato == StatoAutoIscrizione.in_attesa).first()
    if gia_richiesta: raise HTTPException(400, "Richiesta già in attesa di approvazione")

    if corso.richiedi_approvazione_responsabile and responsabili_di(db, user.id):
        r = AutoIscrizioneRichiesta(edizione_id=edizione_id, user_id=user.id)
        db.add(r); db.flush()
        audit_svc.log_from_request(db, request, user, "SELF_ENROLL_REQUEST", entity_type="edizione", entity_id=edizione_id,
                                    entity_name=audit_svc.nome_edizione(db, e), detail="in attesa di approvazione")
        db.commit(); db.refresh(r)
        return {"ok": True, "stato": "in_attesa_approvazione"}

    i = crea_iscrizione_con_capacita(db, e, user.id)
    audit_svc.log_from_request(db, request, user, "SELF_ENROLL", entity_type="edizione", entity_id=edizione_id,
                                entity_name=audit_svc.nome_edizione(db, e), detail=f"stato: {i.stato.value}")
    db.commit()
    if i.stato == StatoIscrizione.iscritto and e.data_inizio:
        invia_invito_calendario(db, e, user.id)
    return {"ok": True, "stato": "iscritto"}

@router.get("/da-approvare")
def da_approvare(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sottoposti_ids = [s.id for s in sottoposti_di(db, user.id)]
    if not sottoposti_ids: return []
    rows = (db.query(AutoIscrizioneRichiesta)
            .filter(AutoIscrizioneRichiesta.user_id.in_(sottoposti_ids), AutoIscrizioneRichiesta.stato == StatoAutoIscrizione.in_attesa)
            .all())
    return [_serialize(r, db) for r in rows]

def _verifica_responsabile_richiedente(db: Session, richiesta_id: str, user_id: str) -> AutoIscrizioneRichiesta:
    r = db.query(AutoIscrizioneRichiesta).filter(AutoIscrizioneRichiesta.id == richiesta_id).first()
    if not r: raise HTTPException(404)
    if r.stato != StatoAutoIscrizione.in_attesa:
        raise HTTPException(400, "Richiesta già gestita")
    if str(r.user_id) not in {str(s.id) for s in sottoposti_di(db, user_id)}:
        raise HTTPException(403, "Non sei il responsabile di questa persona")
    return r

@router.put("/{richiesta_id}/approva")
def approva(richiesta_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = _verifica_responsabile_richiedente(db, richiesta_id, user.id)
    e = db.query(Edizione).filter(Edizione.id == r.edizione_id).first()
    i = crea_iscrizione_con_capacita(db, e, r.user_id)
    r.stato = StatoAutoIscrizione.approvata
    r.valutata_da_id = user.id
    r.valutata_at = datetime.now(timezone.utc)
    audit_svc.log_from_request(db, request, user, "SELF_ENROLL_APPROVE", entity_type="edizione", entity_id=str(e.id),
                                entity_name=audit_svc.nome_edizione(db, e), detail=f"utente: {audit_svc.nome_utente(db, r.user_id)}")
    db.commit()
    if i.stato == StatoIscrizione.iscritto and e.data_inizio:
        invia_invito_calendario(db, e, r.user_id)
    return {"ok": True}

@router.put("/{richiesta_id}/rifiuta")
def rifiuta(richiesta_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = _verifica_responsabile_richiedente(db, richiesta_id, user.id)
    r.stato = StatoAutoIscrizione.rifiutata
    r.valutata_da_id = user.id
    r.valutata_at = datetime.now(timezone.utc)
    e = db.query(Edizione).filter(Edizione.id == r.edizione_id).first()
    audit_svc.log_from_request(db, request, user, "SELF_ENROLL_REJECT", entity_type="edizione", entity_id=str(r.edizione_id),
                                entity_name=audit_svc.nome_edizione(db, e) if e else None,
                                detail=f"utente: {audit_svc.nome_utente(db, r.user_id)}")
    db.commit()
    return {"ok": True}
