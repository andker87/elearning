import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import event
from sqlalchemy.orm import Session

from ..config import settings

# Invii in sottofondo: una richiesta che genera centinaia di notifiche non aspetta l'SMTP,
# e un invio fallito non tocca la transazione.
_esecutore = ThreadPoolExecutor(max_workers=2, thread_name_prefix="invii")


def _esegui(funzione, args):
    try:
        funzione(*args)
    except Exception as e:
        print(f"[invii] {getattr(funzione, '__name__', funzione)} fallito: {e}")


def in_sottofondo(funzione, *args):
    """Per invii che partono dopo il commit (la richiesta non li aspetta)."""
    _esecutore.submit(_esegui, funzione, args)


def dopo_il_commit(db: Session, funzione, *args):
    """Per invii decisi dentro una transazione: partono solo se la transazione va a buon fine
    (se fallisce, niente email per notifiche che non esistono)."""
    db.info.setdefault("invii_in_attesa", []).append((funzione, args))


@event.listens_for(Session, "after_commit")
def _invii_dopo_commit(session):
    for funzione, args in session.info.pop("invii_in_attesa", []):
        in_sottofondo(funzione, *args)


@event.listens_for(Session, "after_rollback")
def _invii_annullati(session):
    session.info.pop("invii_in_attesa", None)

def _oggetto(testo: str) -> str:
    """Un a capo in un header lo spezzerebbe (e l'invio fallirebbe in silenzio): si riduce a una riga."""
    return " ".join((testo or "").split())[:200]


def invia_email(to_email: str, subject: str, body: str) -> bool:
    """Invia un'email se l'SMTP è configurato in ambiente (vedi config.settings);
    altrimenti no-op (True/False solo per sapere se è partita, non deve mai
    bloccare il resto - un invio fallito non deve far fallire la transazione
    che lo ha richiesto)."""
    if not settings.smtp_enabled or not to_email:
        return False
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = _oggetto(subject)
        msg["From"] = settings.SMTP_MITTENTE
        msg["To"] = to_email
        if settings.SMTP_TLS:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT or 587, timeout=10) as server:
                server.starttls()
                if settings.SMTP_USER:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD or "")
                server.sendmail(msg["From"], [to_email], msg.as_string())
        else:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT or 465, timeout=10) as server:
                if settings.SMTP_USER:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD or "")
                server.sendmail(msg["From"], [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"[email] invio a {to_email} fallito: {e}")
        return False

def invia_email_con_allegato(to_email: str, subject: str, body: str,
                              allegato_nome: str, allegato_bytes: bytes, allegato_mime: str = "text/calendar") -> bool:
    """Come invia_email, ma con un file in allegato (es. invito .ics) - stesso
    no-op se l'SMTP non è configurato: un invito calendario via mail non ha
    senso di esistere se non c'è modo di spedirlo."""
    if not settings.smtp_enabled or not to_email:
        return False
    try:
        msg = MIMEMultipart()
        msg["Subject"] = _oggetto(subject)
        msg["From"] = settings.SMTP_MITTENTE
        msg["To"] = to_email
        msg.attach(MIMEText(body, "plain", "utf-8"))
        tipo, _, sottotipo = allegato_mime.partition("/")
        parte = MIMEBase(tipo, sottotipo or "octet-stream")
        parte.set_payload(allegato_bytes)
        encoders.encode_base64(parte)
        parte.add_header("Content-Disposition", f'attachment; filename="{allegato_nome}"')
        msg.attach(parte)
        if settings.SMTP_TLS:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT or 587, timeout=10) as server:
                server.starttls()
                if settings.SMTP_USER:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD or "")
                server.sendmail(msg["From"], [to_email], msg.as_string())
        else:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT or 465, timeout=10) as server:
                if settings.SMTP_USER:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD or "")
                server.sendmail(msg["From"], [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"[email] invio con allegato a {to_email} fallito: {e}")
        return False
