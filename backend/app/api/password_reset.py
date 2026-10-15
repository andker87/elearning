import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models.azienda import Azienda
from ..models.notification import Notification
from ..models.password_reset import PasswordResetToken, RichiestaResetPassword
from ..models.user import User, UserRole
from ..services import audit as audit_svc
from ..services import rate_limit
from ..services.email import invia_email, in_sottofondo
from ..services.inviti import url_base
from ..services.password_policy import password_valida, genera_password_temporanea, REQUISITI_PASSWORD
from ..services.auth import hash_password
from .deps import require_admin_tecnico

router = APIRouter(prefix="/api/auth", tags=["password"])

TOKEN_ORE_VALIDITA = 2
RICHIESTE_PER_IP = 10  # ogni 15 minuti
RICHIESTE_PER_EMAIL = 3  # ogni ora


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class EmailIn(BaseModel):
    email: EmailStr


class ReimpostaIn(BaseModel):
    token: str
    password_nuova: str


@router.post("/password-dimenticata")
def password_dimenticata(data: EmailIn, request: Request, db: Session = Depends(get_db)):
    """Risposta sempre identica, esista o no l'email, per non rivelare chi e' registrato."""
    generica = {"ok": True}
    if not rate_limit.consenti(f"pwd-dimenticata:{audit_svc.ip_client(request)}", RICHIESTE_PER_IP, 15 * 60):
        raise HTTPException(429, "Troppi tentativi, riprova tra qualche minuto.")
    email = data.email.lower().strip()
    # Limite per indirizzo email (oltre a quello per IP, che chi falsifica gli header aggira):
    # non si puo' inondare di messaggi una casella. Stessa risposta, nessun invio.
    if not rate_limit.consenti(f"pwd-email:{email}", RICHIESTE_PER_EMAIL, 3600):
        return generica
    u = db.query(User).filter(func.lower(User.email) == email).first()
    # Chi entra con l'account aziendale ha la password nel dominio: qui non c'e' nulla da reimpostare.
    if not u or not u.is_active or u.origine_credenziali != "locale":
        return generica

    base = url_base(db)
    if settings.smtp_enabled and base:
        for vecchio in db.query(PasswordResetToken).filter(PasswordResetToken.user_id == u.id, PasswordResetToken.usato == False):  # noqa: E712
            vecchio.usato = True
        token = secrets.token_urlsafe(32)
        db.add(PasswordResetToken(user_id=u.id, token_hash=_hash(token),
                                   scade_at=datetime.now(timezone.utc) + timedelta(hours=TOKEN_ORE_VALIDITA)))
        audit_svc.log_from_request(db, request, u, "PASSWORD_RESET_RICHIESTA", entity_type="user", entity_id=str(u.id),
                                    entity_name=u.email, detail="link inviato per email")
        db.commit()
        in_sottofondo(invia_email, u.email, "Reimposta la tua password",
                    f"Hai richiesto di reimpostare la password. Apri questo link entro {TOKEN_ORE_VALIDITA} ore:\n"
                    f"{base}/reimposta-password?token={token}\n\n"
                    "Se non sei stato tu, ignora questa email: la tua password non è stata modificata.")
    else:
        # Nessun canale sicuro verso l'utente: la richiesta passa a un Admin tecnico.
        if not db.query(RichiestaResetPassword).filter(RichiestaResetPassword.user_id == u.id,
                                                       RichiestaResetPassword.stato == "in_attesa").first():
            db.add(RichiestaResetPassword(user_id=u.id))
            audit_svc.log_from_request(db, request, u, "PASSWORD_RESET_RICHIESTA", entity_type="user", entity_id=str(u.id),
                                        entity_name=u.email, detail="in attesa di un Admin tecnico")
            for adm in db.query(User).filter(User.role == UserRole.admin_tecnico, User.is_active == True).all():  # noqa: E712
                db.add(Notification(user_id=adm.id, tipo="richiesta_reset_password",
                                    testo=f"{u.full_name} ha chiesto di reimpostare la password.", link="/reset-password-richieste"))
            db.commit()
    return generica


@router.post("/reimposta-password")
def reimposta_password(data: ReimpostaIn, request: Request, db: Session = Depends(get_db)):
    if not rate_limit.consenti(f"reimposta:{audit_svc.ip_client(request)}", RICHIESTE_PER_IP, 15 * 60):
        raise HTTPException(429, "Troppi tentativi, riprova tra qualche minuto.")
    if not password_valida(data.password_nuova):
        raise HTTPException(400, f"Password non valida: richiesti {REQUISITI_PASSWORD}")
    t = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == _hash(data.token),
                                            PasswordResetToken.usato == False,  # noqa: E712
                                            PasswordResetToken.scade_at > datetime.now(timezone.utc)).with_for_update().first()
    u = db.query(User).filter(User.id == t.user_id).first() if t else None
    if not t or not u or not u.is_active or u.origine_credenziali != "locale":
        raise HTTPException(400, "Link non valido o scaduto: richiedine uno nuovo.")
    u.hashed_password = hash_password(data.password_nuova)
    u.token_version = (u.token_version or 0) + 1
    u.password_da_cambiare = False
    u.tentativi_falliti = 0
    u.bloccato_fino = None
    t.usato = True
    audit_svc.log_from_request(db, request, u, "PASSWORD_RESET_COMPLETATO", entity_type="user", entity_id=str(u.id), entity_name=u.email)
    db.commit()
    return {"ok": True}


# --- Lato Admin tecnico: richieste quando l'email non e' disponibile -----------------

@router.get("/password-reset-richieste")
def richieste(db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    out = []
    for r in db.query(RichiestaResetPassword).order_by(RichiestaResetPassword.created_at.desc()).limit(200).all():
        u = db.query(User).filter(User.id == r.user_id).first()
        out.append({"id": str(r.id), "stato": r.stato, "created_at": r.created_at, "gestita_at": r.gestita_at,
                    "utente": {"nome": u.full_name, "email": u.email} if u else None})
    return {"richieste": out, "smtp_attivo": bool(settings.smtp_enabled)}


@router.post("/password-reset-richieste/{richiesta_id}/genera")
def genera(richiesta_id: str, request: Request, db: Session = Depends(get_db), admin=Depends(require_admin_tecnico)):
    r = db.query(RichiestaResetPassword).filter(RichiestaResetPassword.id == richiesta_id).first()
    if not r or r.stato != "in_attesa":
        raise HTTPException(400, "Nessuna richiesta in attesa con questo id")
    u = db.query(User).filter(User.id == r.user_id).first()
    if not u:
        raise HTTPException(404, "Utente non trovato")
    if not u.is_active or u.origine_credenziali != "locale":
        raise HTTPException(400, "L'account è disattivato o accede con le credenziali aziendali: non c'è una password locale da reimpostare")
    temporanea = genera_password_temporanea()
    u.hashed_password = hash_password(temporanea)
    u.token_version = (u.token_version or 0) + 1
    u.password_da_cambiare = True
    u.tentativi_falliti = 0
    u.bloccato_fino = None
    r.stato = "completata"
    r.gestita_da_id = admin.id
    r.gestita_at = datetime.now(timezone.utc)
    db.add(Notification(user_id=u.id, tipo="password_reset", testo="Un amministratore ti ha assegnato una password temporanea: te la comunicherà a parte. Al primo accesso dovrai sceglierne una tua."))
    audit_svc.log_from_request(db, request, admin, "PASSWORD_RESET_GENERATA", entity_type="user", entity_id=str(u.id), entity_name=u.email,
                                detail="password temporanea assegnata dall'amministratore")
    db.commit()
    return {"ok": True, "password_temporanea": temporanea, "utente": {"nome": u.full_name, "email": u.email}}
