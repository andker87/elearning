import logging
import secrets
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models.user import User
from ..services import audit as audit_svc
from ..services import sso as sso_svc
from ..services.auth import token_per_utente, hash_password
from ..services.percorsi_sync import sincronizza_assegnazioni
from ..services.impronte import impronta
from ..services.persone import dividi_nome

router = APIRouter(prefix="/api/auth/sso", tags=["sso"])


def _errore(db: Session, request: Request, codice: str, dettaglio: str = "") -> RedirectResponse:
    audit_svc.log_from_request(db, request, None, "SSO_LOGIN_FAILED",
                                detail=f"{codice}: {dettaglio}"[:500] if dettaglio else codice)
    db.commit()
    risposta = RedirectResponse(f"/login?sso_errore={quote(codice)}", status_code=302)
    risposta.delete_cookie(sso_svc.COOKIE_TXN, path="/api/auth/sso")
    return risposta


@router.get("/config")
def config():
    return {"enabled": settings.sso_enabled, "label": settings.SSO_LABEL}


@router.get("/login")
def login(request: Request, db: Session = Depends(get_db)):
    if not settings.sso_enabled:
        return RedirectResponse("/login?sso_errore=non_configurato", status_code=302)
    try:
        txn = sso_svc.nuova_transazione()
        url = sso_svc.url_autorizzazione(txn)
    except (httpx.HTTPError, KeyError, ValueError) as e:
        return _errore(db, request, "idp_non_raggiungibile", str(e)[:200])
    risposta = RedirectResponse(url, status_code=302)
    risposta.set_cookie(sso_svc.COOKIE_TXN, sso_svc.firma_transazione(txn), max_age=sso_svc.TXN_DURATA_SECONDI,
                         httponly=True, samesite="lax", path="/api/auth/sso",
                         secure=settings.SSO_PUBLIC_URL.lower().startswith("https://"))
    return risposta


def _nome_dai_dati(claims: dict, email: str) -> tuple:
    """(nome, cognome) dai dati dell'azienda: given_name/family_name se ci sono, altrimenti il nome intero diviso, altrimenti l'email."""
    nome, cognome = (str(claims.get("given_name") or "").strip()[:100], str(claims.get("family_name") or "").strip()[:100])
    if nome and cognome:
        return nome, cognome
    return dividi_nome(str(claims.get("name") or email.split("@")[0]).strip()[:200])


def _risolvi_utente(db: Session, request: Request, sub: str, email: str, claims: dict):
    """Ritorna (utente, evento_audit_dettaglio). Solleva SsoErrore se non ammesso."""
    u = db.query(User).filter(User.sso_subject == sub).first()
    primo_collegamento = False
    if not u:
        u = db.query(User).filter(User.email_idx == impronta(email)).first()
        if u:
            if u.sso_subject and u.sso_subject != sub:
                raise sso_svc.SsoErrore("identita_diversa", email)
            if u.is_admin and not u.sso_subject:
                # Il collegamento al primo accesso si fonda sull'email dichiarata dall'IdP: per
                # l'account piu' potente non basta. L'Admin tecnico entra con la password.
                raise sso_svc.SsoErrore("admin_non_collegabile", email)
            primo_collegamento = True
        elif settings.SSO_PROVISIONA_UTENTI:
            nome_u, cognome_u = _nome_dai_dati(claims, email)
            u = User(email=email, nome=nome_u, cognome=cognome_u, is_external=False,
                     hashed_password=hash_password(secrets.token_urlsafe(32)), origine_credenziali="dominio")
            try:
                with db.begin_nested():
                    db.add(u)
                    db.flush()
            except IntegrityError:
                # un'altra richiesta ha creato lo stesso utente nel frattempo: si riprende quello
                u = db.query(User).filter(User.email_idx == impronta(email)).first()
                if not u:
                    raise
                if u.sso_subject and u.sso_subject != sub:
                    raise sso_svc.SsoErrore("identita_diversa", email)
                if u.is_admin and not u.sso_subject:
                    raise sso_svc.SsoErrore("admin_non_collegabile", email)
            else:
                sincronizza_assegnazioni(db)
                audit_svc.log_from_request(db, request, u, "CREATE", entity_type="user", entity_id=str(u.id),
                                            entity_name=u.email, detail="creato al primo accesso SSO")
            primo_collegamento = True
        else:
            raise sso_svc.SsoErrore("utente_non_abilitato", email)
    if u.is_external:
        raise sso_svc.SsoErrore("esterno_non_ammesso", email)
    if not u.is_active:
        raise sso_svc.SsoErrore("utente_disabilitato", email)
    if primo_collegamento:
        u.sso_subject = sub
        if u.origine_credenziali == "locale":
            u.origine_credenziali = "dominio"
    return u, ("primo collegamento SSO" if primo_collegamento else None)


@router.get("/callback")
def callback(request: Request, code: str = None, state: str = None, error: str = None,
             db: Session = Depends(get_db)):
    if not settings.sso_enabled:
        return RedirectResponse("/login?sso_errore=non_configurato", status_code=302)
    if error:
        return _errore(db, request, "rifiutato_da_idp", error)
    try:
        txn = sso_svc.leggi_transazione(request.cookies.get(sso_svc.COOKIE_TXN, ""))
        if not code or not state or not secrets.compare_digest(state, txn["state"]):
            raise sso_svc.SsoErrore("state_non_valido", "state assente o diverso da quello inviato")
        claims = sso_svc.verifica_id_token(sso_svc.scambia_codice(code, txn["verifier"]), txn["nonce"])
        email = sso_svc.email_da_claims(claims)
        sub = str(claims.get("sub") or "")
        if not sub:
            raise sso_svc.SsoErrore("token_non_valido", "claim sub assente")
        u, nota = _risolvi_utente(db, request, sub, email, claims)
    except sso_svc.SsoErrore as e:
        db.rollback()
        return _errore(db, request, e.codice, e.dettaglio)
    except httpx.HTTPError as e:
        db.rollback()
        return _errore(db, request, "idp_non_raggiungibile", str(e)[:200])
    except Exception as e:  # qualunque imprevisto: l'utente torna alla pagina di accesso con un errore, non su una pagina bianca
        db.rollback()
        logging.getLogger(__name__).exception("SSO: errore inatteso nella callback")
        return _errore(db, request, "errore_interno", type(e).__name__)

    token = token_per_utente(u)
    audit_svc.log_from_request(db, request, u, "LOGIN", entity_type="user", entity_id=str(u.id),
                                entity_name=u.email, detail="SSO" + (f" - {nota}" if nota else ""))
    db.commit()
    risposta = RedirectResponse(f"/login#sso_token={token}", status_code=302)
    risposta.delete_cookie(sso_svc.COOKIE_TXN, path="/api/auth/sso")
    return risposta
