import csv, io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from ..database import get_db
from ..models.test import Gradimento
from ..models.iscrizione import Iscrizione
from ..models.user import User
from .deps import get_current_user, require_training_admin

router = APIRouter(tags=["gradimenti"])

class GradimentoIn(BaseModel):
    voto: int
    commento: Optional[str] = None

@router.post("/api/iscrizioni/{iscrizione_id}/gradimento")
def crea_gradimento(iscrizione_id: str, data: GradimentoIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    i = db.query(Iscrizione).filter(Iscrizione.id == iscrizione_id).first()
    if not i or str(i.user_id) != str(user.id):
        raise HTTPException(403, "Iscrizione non valida per l'utente corrente")
    if data.voto < 1 or data.voto > 5:
        raise HTTPException(400, "Il voto deve essere tra 1 e 5")
    esiste = db.query(Gradimento).filter(Gradimento.iscrizione_id == iscrizione_id).first()
    if esiste:
        raise HTTPException(400, "Gradimento già inviato per questa iscrizione")
    g = Gradimento(iscrizione_id=iscrizione_id, voto=data.voto, commento=data.commento)
    db.add(g); db.commit()
    return {"ok": True}

@router.get("/api/edizioni/{edizione_id}/gradimenti")
def list_gradimenti(edizione_id: str, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    rows = db.query(Gradimento).join(Iscrizione, Gradimento.iscrizione_id == Iscrizione.id).filter(Iscrizione.edizione_id == edizione_id).all()
    out = []
    for g in rows:
        i = db.query(Iscrizione).filter(Iscrizione.id == g.iscrizione_id).first()
        u = db.query(User).filter(User.id == i.user_id).first() if i else None
        out.append({"id": str(g.id), "utente": u.full_name if u else None, "voto": g.voto, "commento": g.commento})
    return out

@router.get("/api/edizioni/{edizione_id}/report/gradimenti.csv")
def report_gradimenti_csv(edizione_id: str, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    rows = db.query(Gradimento).join(Iscrizione, Gradimento.iscrizione_id == Iscrizione.id).filter(Iscrizione.edizione_id == edizione_id).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Utente", "Voto", "Commento"])
    for g in rows:
        i = db.query(Iscrizione).filter(Iscrizione.id == g.iscrizione_id).first()
        u = db.query(User).filter(User.id == i.user_id).first() if i else None
        w.writerow([u.full_name if u else "", g.voto, g.commento or ""])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                              headers={"Content-Disposition": f"attachment; filename=gradimenti_{edizione_id}.csv"})
