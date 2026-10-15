from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ..database import get_db
from ..models.azienda import Azienda
from ..models.push_subscription import PushSubscription
from .deps import get_current_user

router = APIRouter(prefix="/api/push", tags=["push"])

class SubscriptionKeys(BaseModel):
    p256dh: str
    auth: str

class SubscriptionIn(BaseModel):
    endpoint: str
    keys: SubscriptionKeys

class UnsubscribeIn(BaseModel):
    endpoint: str

@router.get("/public-key")
def public_key(db: Session = Depends(get_db), user=Depends(get_current_user)):
    a = db.query(Azienda).first()
    return {"public_key": a.vapid_public_key if a else None}

@router.get("/stato")
def stato(db: Session = Depends(get_db), user=Depends(get_current_user)):
    n = db.query(PushSubscription).filter(PushSubscription.user_id == user.id).count()
    return {"dispositivi_registrati": n}

@router.post("/subscribe")
def subscribe(data: SubscriptionIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    for _ in range(2):  # due richieste insieme con lo stesso endpoint: la seconda trova la riga creata dalla prima
        esistente = db.query(PushSubscription).filter(PushSubscription.endpoint == data.endpoint).first()
        if esistente:
            esistente.user_id = user.id
            esistente.p256dh = data.keys.p256dh
            esistente.auth = data.keys.auth
        else:
            db.add(PushSubscription(user_id=user.id, endpoint=data.endpoint, p256dh=data.keys.p256dh, auth=data.keys.auth))
        try:
            db.commit()
            return {"ok": True}
        except IntegrityError:
            db.rollback()
    raise HTTPException(409, "Sottoscrizione non salvata: riprova")  # due tentativi falliti: non si dice "ok" se non e' stato salvato

@router.post("/unsubscribe")
def unsubscribe(data: UnsubscribeIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    db.query(PushSubscription).filter(
        PushSubscription.endpoint == data.endpoint, PushSubscription.user_id == user.id
    ).delete(synchronize_session=False)
    db.commit()
    return {"ok": True}
