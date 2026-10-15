import ipaddress
from sqlalchemy.orm import Session
from fastapi import Request
from ..config import settings
from ..models.audit import AuditLog

def _ip_valido(testo):
    try:
        return ipaddress.ip_address((testo or "").strip())
    except ValueError:
        return None


def _fiduciario(ip) -> bool:
    return ip is not None and any(ip in rete for rete in settings.reti_fiduciarie)


def ip_client(request: Request):
    """IP del client, calcolato senza fidarsi di chi puo' scrivere gli header.
    Il nginx della piattaforma mette in X-Real-IP l'indirizzo di chi gli si connette (e lo
    sovrascrive sempre). Se quell'indirizzo non e' un proxy dichiarato in PROXY_FIDUCIARI,
    e' il client e basta: gli altri header si ignorano. Se e' un proxy fidato, si leggono
    CF-Connecting-IP o la catena X-Forwarded-For da destra a sinistra, fermandosi al primo
    indirizzo non fidato: un valore falso aggiunto dal client sta a sinistra e non si raggiunge."""
    if not request:
        return None
    h = request.headers
    peer = _ip_valido(h.get("x-real-ip")) or _ip_valido(request.client.host if request.client else None)
    if peer is None:
        return request.client.host if request.client else None
    if not _fiduciario(peer):
        return str(peer)
    if settings.PROXY_CLOUDFLARE:
        cf = _ip_valido(h.get("cf-connecting-ip"))
        if cf is not None:
            return str(cf)
    catena = [_ip_valido(x) for x in h.get("x-forwarded-for", "").split(",")]
    for ip in reversed([x for x in catena if x is not None]):
        if not _fiduciario(ip):
            return str(ip)
    return str(peer)


def log_from_request(db: Session, request: Request, user, action: str,
                      entity_type: str = None, entity_id: str = None,
                      entity_name: str = None, detail: str = None):
    entry = AuditLog(
        user_id=getattr(user, "id", None),
        user_email=getattr(user, "email", None),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        detail=detail,
        ip_address=ip_client(request),
    )
    db.add(entry)
    db.flush()


def nome_utente(db: Session, uid) -> str:
    from ..models.user import User
    u = db.query(User).filter(User.id == uid).first()
    return u.email if u else str(uid)


def nome_edizione(db: Session, e) -> str:
    from ..models.corso import Corso
    corso = db.query(Corso).filter(Corso.id == e.corso_id).first()
    titolo = corso.titolo if corso else "Sessione"
    return f"{titolo} ({e.data_inizio.strftime('%d/%m/%Y')})" if e.data_inizio else f"{titolo} (senza data)"
