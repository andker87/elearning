"""Invito a scegliere la propria password, al posto di una password spedita per email.

Un nuovo utente riceve un link monouso (valido alcuni giorni) per impostare da solo la
password: nessun segreto viaggia per posta. Il link usa lo stesso meccanismo del reset
(PasswordResetToken). Serve un invio email attivo e l'URL pubblico della piattaforma:
senza, l'amministratore riceve una password temporanea da comunicare a parte."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..config import settings
from ..models.azienda import Azienda
from ..models.password_reset import PasswordResetToken
from .email import invia_email

TOKEN_ORE_INVITO = 72


def url_base(db: Session) -> str:
    """URL da mettere nei link inviati per email: solo quello configurato (pagina Piattaforma o
    SSO_PUBLIC_URL), mai un indirizzo preso dalla richiesta."""
    a = db.query(Azienda).first()
    return ((a.url_pubblico if a else None) or "").strip().rstrip("/") or (settings.SSO_PUBLIC_URL or "").strip().rstrip("/")


def canale_email_disponibile(db: Session) -> bool:
    return bool(settings.smtp_enabled and url_base(db))


def crea_link_invito(db: Session, utente) -> Optional[str]:
    """Crea il token e restituisce il link (None se non c'e' un canale email). Non fa commit."""
    if not canale_email_disponibile(db):
        return None
    token = secrets.token_urlsafe(32)
    db.add(PasswordResetToken(user_id=utente.id, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                              scade_at=datetime.now(timezone.utc) + timedelta(hours=TOKEN_ORE_INVITO)))
    db.flush()
    return f"{url_base(db)}/reimposta-password?token={token}"


def invia_invito(email: str, nome: str, link: str) -> bool:
    return invia_email(email, "Account piattaforma formazione creato",
                       f"Ciao {nome},\nè stato creato il tuo account sulla piattaforma di formazione.\n\n"
                       f"Scegli la tua password da questo link, valido {TOKEN_ORE_INVITO // 24} giorni:\n{link}\n\n"
                       f"Il tuo indirizzo di accesso è {email}.")
