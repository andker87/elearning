from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from ..database import get_db
from ..models.user import User, UserRole
from ..models.group import Group, UserGroup
from ..services.auth import verify_password, hash_password, create_access_token
from ..services import audit as audit_svc
from ..services.percorsi_sync import sincronizza_assegnazioni
from .deps import get_current_user, require_training_admin, require_admin_tecnico

router = APIRouter(prefix="/api/auth", tags=["auth"])

class LoginRequest(BaseModel):
    email: EmailStr; password: str

class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: UserRole = UserRole.user
    is_external: bool = False
    organizzazione_id: Optional[str] = None
    group_ids: List[str] = []
    data_ingresso: Optional[datetime] = None
    origine_credenziali: str = "locale"

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None
    role: Optional[UserRole] = None
    is_external: Optional[bool] = None
    organizzazione_id: Optional[str] = None
    group_ids: Optional[List[str]] = None
    manager_id: Optional[str] = None
    can_see_all: Optional[bool] = None
    data_ingresso: Optional[datetime] = None
    origine_credenziali: Optional[str] = None

def _is_docente_di_qualcosa(user_id, db: Session) -> bool:
    from ..models.edizione import EdizioneDocente
    return db.query(EdizioneDocente).filter(EdizioneDocente.user_id == user_id).first() is not None

def _serialize_user(u: User, db: Session):
    memberships = db.query(UserGroup).options(joinedload(UserGroup.group)).filter(UserGroup.user_id == u.id).all()
    groups = [{"id": str(m.group_id), "name": m.group.name, "color": m.group.color} for m in memberships if m.group]
    return {
        "id": str(u.id), "email": u.email, "full_name": u.full_name,
        "role": u.role, "is_active": u.is_active,
        "is_external": u.is_external,
        "organizzazione_id": str(u.organizzazione_id) if u.organizzazione_id else None,
        "manager_id": str(u.manager_id) if u.manager_id else None,
        "can_see_all": u.can_see_all or False,
        "data_ingresso": u.data_ingresso,
        "origine_credenziali": u.origine_credenziali,
        "is_docente": _is_docente_di_qualcosa(u.id, db),
        "groups": groups, "created_at": u.created_at,
    }

def _assign_groups(user_id: str, group_ids: List[str], db: Session):
    db.query(UserGroup).filter(UserGroup.user_id == user_id).delete()
    for gid in group_ids:
        db.add(UserGroup(user_id=user_id, group_id=gid))
    db.flush()

@router.post("/login")
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.hashed_password):
        audit_svc.log_from_request(db, request, None, "LOGIN_FAILED", detail=f"Tentativo fallito: {data.email}")
        db.commit()
        raise HTTPException(401, "Credenziali non valide")
    if not user.is_active:
        raise HTTPException(401, "Utente disabilitato")
    token = create_access_token({"sub": user.email})
    audit_svc.log_from_request(db, request, user, "LOGIN", entity_type="user", entity_id=str(user.id), entity_name=user.email)
    db.commit()
    return {"access_token": token, "token_type": "bearer", "user": _serialize_user(user, db)}

@router.get("/me")
def me(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _serialize_user(user, db)

@router.put("/me/password")
def cambia_password(data: PasswordChange, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.origine_credenziali != "locale":
        raise HTTPException(400, "Le credenziali sono gestite centralmente: non puoi cambiare la password da qui")
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(400, "Password attuale non corretta")
    if len(data.new_password) < 6:
        raise HTTPException(400, "Password troppo corta (minimo 6 caratteri)")
    user.hashed_password = hash_password(data.new_password)
    db.commit()
    return {"ok": True}

@router.get("/users")
def list_users(db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    users = db.query(User).order_by(User.full_name).all()
    return [_serialize_user(u, db) for u in users]

@router.get("/users/simple")
def list_users_simple(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Lista semplificata utenti attivi - usata per i picker (es. scelta docenti)."""
    users = db.query(User).filter(User.is_active == True).order_by(User.full_name).all()
    return [{"id": str(u.id), "full_name": u.full_name, "email": u.email, "is_external": u.is_external} for u in users]

@router.post("/users")
def create_user(data: UserCreate, request: Request, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(400, "Email già esistente")
    if data.is_external and not data.organizzazione_id:
        raise HTTPException(400, "Un utente esterno deve avere un'organizzazione di riferimento")
    u = User(
        email=data.email, full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role, is_external=data.is_external,
        organizzazione_id=data.organizzazione_id,
        data_ingresso=data.data_ingresso,
        origine_credenziali=data.origine_credenziali,
    )
    db.add(u); db.flush()
    if data.group_ids:
        _assign_groups(str(u.id), data.group_ids, db)
    audit_svc.log_from_request(db, request, user, "CREATE", entity_type="user", entity_id=str(u.id), entity_name=u.email)
    sincronizza_assegnazioni(db)
    db.commit(); db.refresh(u)
    return _serialize_user(u, db)

@router.put("/users/{user_id}")
def update_user(user_id: str, data: UserUpdate, request: Request,
                 db: Session = Depends(get_db), current=Depends(require_admin_tecnico)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u: raise HTTPException(404)
    if data.full_name is not None: u.full_name = data.full_name
    if data.is_active is not None: u.is_active = data.is_active
    if data.password: u.hashed_password = hash_password(data.password)
    if data.role is not None: u.role = data.role
    if data.is_external is not None: u.is_external = data.is_external
    if data.organizzazione_id is not None: u.organizzazione_id = data.organizzazione_id or None
    if u.is_external and not u.organizzazione_id:
        raise HTTPException(400, "Un utente esterno deve avere un'organizzazione di riferimento")
    if data.group_ids is not None: _assign_groups(user_id, data.group_ids, db)
    if data.manager_id is not None: u.manager_id = data.manager_id or None
    if data.can_see_all is not None: u.can_see_all = data.can_see_all
    if data.data_ingresso is not None: u.data_ingresso = data.data_ingresso
    if data.origine_credenziali is not None: u.origine_credenziali = data.origine_credenziali
    audit_svc.log_from_request(db, request, current, "UPDATE", entity_type="user", entity_id=str(u.id), entity_name=u.email)
    sincronizza_assegnazioni(db)
    db.commit()
    return _serialize_user(u, db)
