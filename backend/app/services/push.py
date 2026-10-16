import json
import logging
from py_vapid import Vapid01
from pywebpush import webpush, WebPushException
from sqlalchemy.orm import Session
from ..models.azienda import Azienda
from ..models.push_subscription import PushSubscription
from .cifratura import decifra_testo

log = logging.getLogger(__name__)

def _vapid(db: Session):
    a = db.query(Azienda).first()
    if not a or not a.vapid_private_key:
        return None
    return Vapid01.from_pem(decifra_testo(a.vapid_private_key).encode())

def _spedisci(vapid_pem: str, sottoscrizioni: list, payload: str):
    """Gira in sottofondo: niente sessione della richiesta, ne apre una sua solo per togliere le scadute."""
    vapid = Vapid01.from_pem(vapid_pem.encode())
    scadute = []
    for sub_id, endpoint, p256dh, auth in sottoscrizioni:
        try:
            webpush(subscription_info={"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}}, data=payload,
                    vapid_private_key=vapid, vapid_claims={"sub": "mailto:noreply@piattaforma-formazione.local"}, timeout=10)
        except WebPushException as e:
            status = e.response.status_code if e.response is not None else None
            if status in (404, 410):
                scadute.append(sub_id)
            else:
                log.warning("push: invio a %s fallito: %s", endpoint, e)
        except Exception as e:
            log.warning("push: invio a %s fallito: %s", endpoint, e)
    if scadute:
        from ..database import SessionLocal
        db = SessionLocal()
        try:
            db.query(PushSubscription).filter(PushSubscription.id.in_(scadute)).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


def accoda_push(db: Session, user_id, title: str, body: str, url: str = None):
    """Notifica push a tutti i dispositivi sottoscritti dall'utente. Non blocca mai il chiamante: la spedizione
    avviene dopo il commit e fuori dalla richiesta, un fallimento e' solo registrato nel log. Una sottoscrizione
    scaduta o revocata dal browser (404/410) viene rimossa da _spedisci."""
    from .email import dopo_il_commit
    a = db.query(Azienda).first()
    if not a or not a.vapid_private_key:
        return
    subs = [(s.id, s.endpoint, s.p256dh, s.auth) for s in db.query(PushSubscription).filter(PushSubscription.user_id == user_id).all()]
    if subs:
        dopo_il_commit(db, _spedisci, decifra_testo(a.vapid_private_key), subs, json.dumps({"title": title, "body": body, "url": url or "/"}))
