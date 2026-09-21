from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.notification import Notification
from ..services.notifiche import genera_notifiche
from .deps import get_current_user, require_training_admin

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

@router.post("/genera")
def genera(db: Session = Depends(get_db), user=Depends(require_training_admin)):
    """Esegue subito il controllo scadenze/promemoria, invece di aspettare lo
    scheduler giornaliero - utile per verificare o forzare un aggiornamento."""
    creati = genera_notifiche(db)
    return {"ok": True, "create": creati}

@router.get("")
def list_notifications(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(50).all()
    return [{"id": str(n.id), "tipo": n.tipo, "testo": n.testo, "link": n.link,
             "letta": n.letta, "created_at": n.created_at} for n in rows]

@router.post("/{notification_id}/letta")
def segna_letta(notification_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    n = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == user.id).first()
    if not n: raise HTTPException(404)
    n.letta = True
    db.commit()
    return {"ok": True}
