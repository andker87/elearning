from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.user import User, UserRole
from ..services.auth import decode_token

bearer = HTTPBearer()

# Con una password assegnata da altri si puo' solo vedere il proprio profilo e sceglierne una propria.
PERCORSI_CAMBIO_PASSWORD = ("/api/auth/me", "/api/auth/me/password")

def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db)
):
    payload = decode_token(credentials.credentials)
    if not payload: raise HTTPException(status_code=401, detail="Token non valido")
    user = db.query(User).filter(User.email == payload.get("sub")).first()
    if not user or not user.is_active: raise HTTPException(status_code=401, detail="Utente non trovato")
    if payload.get("tv", 0) != (user.token_version or 0):
        raise HTTPException(status_code=401, detail="Sessione scaduta: accedi di nuovo")
    if user.password_da_cambiare and user.origine_credenziali == "locale" and request.url.path not in PERCORSI_CAMBIO_PASSWORD:
        raise HTTPException(status_code=403, detail="Devi prima scegliere una nuova password")
    return user

def require_admin_tecnico(user: User = Depends(get_current_user)):
    if user.role != UserRole.admin_tecnico:
        raise HTTPException(status_code=403, detail="Richiesto ruolo Admin tecnico")
    return user

def require_training_admin(user: User = Depends(get_current_user)):
    if user.role not in (UserRole.admin_tecnico, UserRole.training_admin):
        raise HTTPException(status_code=403, detail="Richiesto ruolo Ufficio Formazione o Admin tecnico")
    return user
