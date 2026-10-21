"""Richieste di iscrizione dei responsabili: le gestisce la Formazione (approva o rifiuta)."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.corso import Corso
from ..models.edizione import Edizione, StatoEdizione
from ..models.group import UserGroup
from ..models.iscrizione import StatoIscrizione
from ..models.notification import Notification
from ..models.richiesta_iscrizione import RichiestaIscrizione
from ..models.user import User
from ..services import audit as audit_svc
from ..services.durata import durata_effettiva
from ..services.email import dopo_il_commit, invia_email
from ..services.iscrizioni import crea_iscrizione_con_capacita, posti_occupati, sessione_finita
from ..services.notifiche import invia_invito_calendario
from .deps import require_training_admin

router = APIRouter(prefix="/api/richieste-iscrizione", tags=["richieste-iscrizione"])


def _riga(r: RichiestaIscrizione, db: Session) -> dict:
    e = db.query(Edizione).filter(Edizione.id == r.edizione_id).first()
    c = db.query(Corso).filter(Corso.id == e.corso_id).first() if e else None
    persona = db.query(User).filter(User.id == r.user_id).first()
    richiedente = db.query(User).filter(User.id == r.richiedente_id).first()
    ufficio = db.query(UserGroup).filter(UserGroup.user_id == r.user_id).first()
    return {"id": str(r.id), "stato": r.stato, "created_at": r.created_at, "valutata_at": r.valutata_at, "motivo_rifiuto": r.motivo_rifiuto,
            "persona": persona.full_name if persona else None, "ufficio": ufficio.group.name if ufficio and ufficio.group else None,
            "richiedente": richiedente.full_name if richiedente else None, "autorichiesta": _autorichiesta(r),
            "edizione_id": str(r.edizione_id), "corso_titolo": c.titolo if c else None,
            "edizione_stato": e.stato if e else None, "modalita": e.modalita if e else None,
            "data_inizio": e.data_inizio if e else None, "data_fine": e.data_fine if e else None, "luogo": e.luogo if e else None,
            "durata_effettiva_minuti": durata_effettiva(e, c) if e else None,
            "posti_liberi": (e.posti_max - posti_occupati(db, e.id)) if e and e.posti_max else None}


@router.get("")
def elenco(db: Session = Depends(get_db), user: User = Depends(require_training_admin)):
    in_attesa = db.query(RichiestaIscrizione).filter(RichiestaIscrizione.stato == "in_attesa").order_by(RichiestaIscrizione.created_at).all()
    gestite = db.query(RichiestaIscrizione).filter(RichiestaIscrizione.stato != "in_attesa").order_by(RichiestaIscrizione.valutata_at.desc().nullslast()).limit(50).all()
    return {"in_attesa": [_riga(r, db) for r in in_attesa], "gestite": [_riga(r, db) for r in gestite]}


def _da_gestire(db: Session, richiesta_id: str) -> RichiestaIscrizione:
    r = db.query(RichiestaIscrizione).filter(RichiestaIscrizione.id == richiesta_id).with_for_update().first()   # due Formazione insieme: la seconda aspetta e vede l'esito
    if not r:
        raise HTTPException(404)
    if r.stato != "in_attesa":
        raise HTTPException(400, "Richiesta già gestita")
    return r


def _nome(db: Session, user_id) -> str:
    u = db.query(User).filter(User.id == user_id).first()
    return u.full_name if u else "la persona"


def _autorichiesta(r: RichiestaIscrizione) -> bool:
    """La persona ha chiesto per se' (iscrizione «con approvazione della Formazione»), non un responsabile per lei."""
    return str(r.richiedente_id) == str(r.user_id)


def _avvisa_richiedente(db: Session, r: RichiestaIscrizione, testo: str, oggetto: str):
    richiedente = db.query(User).filter(User.id == r.richiedente_id).first()
    if richiedente:
        db.add(Notification(user_id=richiedente.id, tipo="richiesta_iscrizione_esito", testo=testo, link="/miei-corsi" if _autorichiesta(r) else "/risorse"))
        dopo_il_commit(db, invia_email, richiedente.email, oggetto, testo)


@router.put("/{richiesta_id}/approva")
def approva(richiesta_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(require_training_admin)):
    r = _da_gestire(db, richiesta_id)
    e = db.query(Edizione).filter(Edizione.id == r.edizione_id).first()
    if not e or e.stato not in (StatoEdizione.pianificata, StatoEdizione.in_corso) or sessione_finita(e):
        raise HTTPException(400, "La sessione non è più aperta alle iscrizioni: rifiuta la richiesta")
    persona_u = db.query(User).filter(User.id == r.user_id).first()
    if not persona_u or not persona_u.is_active:
        raise HTTPException(400, "La persona non è più attiva: rifiuta la richiesta")
    i = crea_iscrizione_con_capacita(db, e, r.user_id)       # rispetta posti e lista d'attesa; se non c'e' posto la richiesta resta in attesa
    r.stato = "approvata"
    r.valutata_da_id = user.id
    r.valutata_at = datetime.now(timezone.utc)
    persona = audit_svc.nome_utente(db, r.user_id)          # nel registro attivita' l'identificativo e' l'email
    nome = _nome(db, r.user_id)
    in_attesa = " (in lista d'attesa)" if i.stato != StatoIscrizione.iscritto else ""
    c = db.query(Corso).filter(Corso.id == e.corso_id).first()
    soggetto = "la tua iscrizione" if _autorichiesta(r) else f"l'iscrizione di {nome}"
    _avvisa_richiedente(db, r, f"Richiesta approvata: {soggetto} alla sessione di «{c.titolo if c else ''}» è confermata{in_attesa}.", "Richiesta di iscrizione approvata")
    audit_svc.log_from_request(db, request, user, "TEAM_REQUEST_APPROVE", entity_type="edizione", entity_id=str(e.id),
                                entity_name=audit_svc.nome_edizione(db, e), detail=f"persona: {persona} - stato: {i.stato.value}")
    db.commit()
    if i.stato == StatoIscrizione.iscritto and e.data_inizio:
        invia_invito_calendario(db, e, r.user_id)
    return {"ok": True, "stato_iscrizione": i.stato}


class RifiutoIn(BaseModel):
    motivo: Optional[str] = None


@router.put("/{richiesta_id}/rifiuta")
def rifiuta(richiesta_id: str, data: RifiutoIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_training_admin)):
    r = _da_gestire(db, richiesta_id)
    r.stato = "rifiutata"
    r.motivo_rifiuto = (data.motivo or "").strip() or None
    r.valutata_da_id = user.id
    r.valutata_at = datetime.now(timezone.utc)
    e = db.query(Edizione).filter(Edizione.id == r.edizione_id).first()
    c = db.query(Corso).filter(Corso.id == e.corso_id).first() if e else None
    persona = audit_svc.nome_utente(db, r.user_id)
    soggetto = "la tua iscrizione" if _autorichiesta(r) else f"l'iscrizione di {_nome(db, r.user_id)}"
    _avvisa_richiedente(db, r, f"Richiesta rifiutata: {soggetto} alla sessione di «{c.titolo if c else ''}»" + (f" ({r.motivo_rifiuto})." if r.motivo_rifiuto else "."),
                        "Richiesta di iscrizione rifiutata")
    audit_svc.log_from_request(db, request, user, "TEAM_REQUEST_REJECT", entity_type="edizione", entity_id=str(r.edizione_id),
                                entity_name=audit_svc.nome_edizione(db, e) if e else None, detail=f"persona: {persona}")
    db.commit()
    return {"ok": True}
