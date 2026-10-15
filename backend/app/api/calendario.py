import secrets
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.user import User
from ..models.edizione import Edizione, EdizioneDocente
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.corso import Corso
from ..services.calendario import evento_edizione, costruisci_ics
from ..services import audit as audit_svc
from .deps import get_current_user

router = APIRouter(prefix="/api/calendario", tags=["calendario"])

@router.get("/url")
def url_feed(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.calendar_token:
        user.calendar_token = secrets.token_urlsafe(24)
        db.commit()
    return {"url": f"/api/calendario/feed.ics?token={user.calendar_token}"}

@router.post("/url/rigenera")
def rigenera_url_feed(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    user.calendar_token = secrets.token_urlsafe(24)
    audit_svc.log_from_request(db, request, user, "REGENERATE_CALENDAR_TOKEN", entity_type="user", entity_id=str(user.id), entity_name=user.email)
    db.commit()
    return {"url": f"/api/calendario/feed.ics?token={user.calendar_token}"}

@router.get("/feed.ics")
def feed(token: str, db: Session = Depends(get_db)):
    """Niente Bearer qui: è l'URL che Outlook/Google Calendar interrogano
    periodicamente da soli per aggiornare l'abbonamento, senza un utente
    davanti che possa fornire un token di sessione - il token nell'URL
    stesso è l'unica autenticazione possibile in questo scenario."""
    user = db.query(User).filter(User.calendar_token == token, User.is_active == True).first()  # noqa: E712
    if not user:
        raise HTTPException(404, "Link non valido")
    edizioni_ids = {i.edizione_id for i in db.query(Iscrizione).filter(
        Iscrizione.user_id == user.id,
        Iscrizione.stato.in_([StatoIscrizione.iscritto, StatoIscrizione.in_lista_attesa]),
    ).all()}
    edizioni_ids |= {d.edizione_id for d in db.query(EdizioneDocente).filter(EdizioneDocente.user_id == user.id).all()}
    eventi = []
    edizioni = db.query(Edizione).filter(Edizione.id.in_(edizioni_ids)).all() if edizioni_ids else []
    titoli = {c.id: c.titolo for c in db.query(Corso).filter(Corso.id.in_({e.corso_id for e in edizioni})).all()} if edizioni else {}
    for e in edizioni:
        ev = evento_edizione(e, titoli.get(e.corso_id, "Sessione formativa"))
        if ev:
            eventi.append(ev)
    ics = costruisci_ics(eventi)
    return Response(content=ics, media_type="text/calendar; charset=utf-8",
                     headers={"Content-Disposition": "inline; filename=formazione.ics"})
