from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from ..database import get_db
from ..models.user import User
from ..services.auth import hash_password
from ..services.password_policy import password_valida, REQUISITI_PASSWORD

router = APIRouter(prefix="/api/setup", tags=["setup"])

class SetupInit(BaseModel):
    nome: str
    cognome: str
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
    if not password_valida(data.password):
        raise HTTPException(400, f"Password non valida: richiesti {REQUISITI_PASSWORD}")

    user = User(
        email=data.email,
        nome=data.nome.strip(),
        cognome=data.cognome.strip(),
        hashed_password=hash_password(data.password),
        is_admin=True,
        is_active=True,
    )
    db.add(user); db.flush()
    db.commit()

    return {"ok": True, "message": "Piattaforma configurata con successo"}
