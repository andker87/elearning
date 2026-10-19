import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from ..services import cifratura
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.certificato import Certificato
from ..models.iscrizione import Iscrizione
from .deps import get_current_user

router = APIRouter(prefix="/api/certificati", tags=["certificati"])

@router.get("/verifica/{codice}")
def verifica_certificato(codice: str, db: Session = Depends(get_db)):
    """Endpoint pubblico (nessuna autenticazione): chiunque abbia il codice
    stampato sull'attestato può verificarne l'autenticità - es. un ispettore."""
    c = db.query(Certificato).filter(Certificato.codice_verifica == codice).first()
    if not c:
        raise HTTPException(404, "Codice non valido")
    return {"valido": True, "emesso_at": c.emesso_at, "tipo": c.tipo}

@router.get("/mie")
def miei_certificati(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(Certificato).join(Iscrizione, Certificato.iscrizione_id == Iscrizione.id).filter(Iscrizione.user_id == user.id).all()
    return [{"id": str(c.id), "codice_verifica": c.codice_verifica, "emesso_at": c.emesso_at} for c in rows]

@router.get("/{certificato_id}/pdf")
def scarica_pdf(certificato_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = db.query(Certificato).filter(Certificato.id == certificato_id).first()
    if not c or not c.pdf_path:
        raise HTTPException(404)
    i = db.query(Iscrizione).filter(Iscrizione.id == c.iscrizione_id).first()
    if str(i.user_id) != str(user.id) and not user.ha_poteri_formazione:
        raise HTTPException(403)
    if not os.path.exists(c.pdf_path):
        raise HTTPException(404)
    return Response(cifratura.leggi_file(c.pdf_path), media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="attestato.pdf"', "Cache-Control": "private, no-store"})
