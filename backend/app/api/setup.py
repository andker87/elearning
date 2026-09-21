from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from ..database import get_db
from ..models.user import User, UserRole
from ..models.group import Group, UserGroup
from ..services.auth import hash_password

router = APIRouter(prefix="/api/setup", tags=["setup"])

SYSTEM_GROUPS = [
    {
        "name": "Admin", "description": "Gestione tecnica della piattaforma",
        "color": "#e84a4a", "is_system": True, "permissions": {}, "sort_order": "0",
    },
    {
        "name": "Ufficio Formazione", "description": "Gestisce corsi, edizioni, iscrizioni e certificati",
        "color": "#4a7eff", "is_system": True,
        "permissions": {s: "write" for s in ["corsi", "percorsi", "edizioni", "iscrizioni", "certificati", "organizzazioni", "utenti"]},
        "sort_order": "1",
    },
    {
        "name": "Formatori", "description": "Persone abilitate a tenere edizioni come docenti",
        "color": "#22a587", "is_system": True, "permissions": {}, "sort_order": "2",
    },
    {
        "name": "Utenti", "description": "Accesso ai propri corsi/edizioni",
        "color": "#5a6b8a", "is_system": True, "permissions": {}, "sort_order": "3",
    },
]

class SetupInit(BaseModel):
    full_name: str
    email: EmailStr
    password: str

@router.get("/status")
def setup_status(db: Session = Depends(get_db)):
    configured = db.query(User).count() > 0
    return {"configured": configured}

@router.post("/init")
def setup_init(data: SetupInit, db: Session = Depends(get_db)):
    if db.query(User).count() > 0:
        raise HTTPException(400, "Piattaforma già configurata")
    if len(data.password) < 6:
        raise HTTPException(400, "Password troppo corta (minimo 6 caratteri)")

    groups = {}
    for gdata in SYSTEM_GROUPS:
        existing = db.query(Group).filter(Group.name == gdata["name"], Group.is_system == True).first()
        if not existing:
            g = Group(**gdata)
            db.add(g); db.flush()
            groups[gdata["name"]] = g
        else:
            groups[gdata["name"]] = existing

    user = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=UserRole.admin_tecnico,
        is_active=True,
    )
    db.add(user); db.flush()
    db.add(UserGroup(user_id=user.id, group_id=groups["Admin"].id))
    db.commit()

    return {"ok": True, "message": "Piattaforma configurata con successo"}
