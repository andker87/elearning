import json
from py_vapid import Vapid01
from pywebpush import webpush, WebPushException
from sqlalchemy.orm import Session
from ..models.azienda import Azienda
from ..models.push_subscription import PushSubscription

def _vapid(db: Session):
    a = db.query(Azienda).first()
    if not a or not a.vapid_private_key:
        return None
    return Vapid01.from_pem(a.vapid_private_key.encode())

def invia_push(db: Session, user_id, title: str, body: str, url: str = None) -> int:
    """Invia una notifica push a tutti i dispositivi sottoscritti da questo
    utente. Non deve mai bloccare il chiamante (stesso principio di
    invia_email): un fallimento è loggato, mai sollevato. Una sottoscrizione
    scaduta/revocata dal browser (404/410) viene rimossa qui, è l'unico modo
    per saperlo."""
    vapid = _vapid(db)
    if not vapid:
        return 0
    sottoscrizioni = db.query(PushSubscription).filter(PushSubscription.user_id == user_id).all()
    payload = json.dumps({"title": title, "body": body, "url": url or "/"})
    inviate = 0
    for sub in sottoscrizioni:
        try:
            webpush(
                subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
                data=payload,
                vapid_private_key=vapid,
                vapid_claims={"sub": "mailto:noreply@piattaforma-formazione.local"},
                timeout=10,
            )
            inviate += 1
        except WebPushException as e:
            status = e.response.status_code if e.response is not None else None
            if status in (404, 410):
                db.query(PushSubscription).filter(PushSubscription.id == sub.id).delete(synchronize_session=False)
                db.commit()
            else:
                print(f"[push] invio a {sub.endpoint} fallito: {e}")
        except Exception as e:
            print(f"[push] invio a {sub.endpoint} fallito: {e}")
    return inviate


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
                print(f"[push] invio a {endpoint} fallito: {e}")
        except Exception as e:
            print(f"[push] invio a {endpoint} fallito: {e}")
    if scadute:
        from ..database import SessionLocal
        db = SessionLocal()
        try:
            db.query(PushSubscription).filter(PushSubscription.id.in_(scadute)).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


def accoda_push(db: Session, user_id, title: str, body: str, url: str = None):
    """Come invia_push, ma la spedizione avviene dopo il commit e fuori dalla richiesta."""
    from .email import dopo_il_commit
    a = db.query(Azienda).first()
    if not a or not a.vapid_private_key:
        return
    subs = [(s.id, s.endpoint, s.p256dh, s.auth) for s in db.query(PushSubscription).filter(PushSubscription.user_id == user_id).all()]
    if subs:
        dopo_il_commit(db, _spedisci, a.vapid_private_key, subs, json.dumps({"title": title, "body": body, "url": url or "/"}))
