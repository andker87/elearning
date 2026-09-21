from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.user import User, UserRole
from ..services.auth import decode_token

bearer = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db)
):
    payload = decode_token(credentials.credentials)
    if not payload: raise HTTPException(status_code=401, detail="Token non valido")
    user = db.query(User).filter(User.email == payload.get("sub")).first()
    if not user or not user.is_active: raise HTTPException(status_code=401, detail="Utente non trovato")
    return user

def require_admin_tecnico(user: User = Depends(get_current_user)):
    if user.role != UserRole.admin_tecnico:
        raise HTTPException(status_code=403, detail="Richiesto ruolo Admin tecnico")
    return user

def require_training_admin(user: User = Depends(get_current_user)):
    if user.role not in (UserRole.admin_tecnico, UserRole.training_admin):
        raise HTTPException(status_code=403, detail="Richiesto ruolo Ufficio Formazione o Admin tecnico")
    return user
