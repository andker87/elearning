import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from ..services import cifratura
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.certificato import Certificato
from ..models.corso import Corso
from ..models.edizione import Edizione
from ..models.iscrizione import Iscrizione
from ..models.user import User
from ..services.certificati import nome_file_attestato
from ..services.durata import durata_effettiva
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

def _nome_file(db: Session, c: Certificato, i: Iscrizione) -> str:
    u = db.query(User).filter(User.id == i.user_id).first()
    e = db.query(Edizione).filter(Edizione.id == i.edizione_id).first()
    corso = db.query(Corso).filter(Corso.id == e.corso_id).first() if e else None
    return nome_file_attestato(corso.titolo if corso else "Attestato", u.cognome if u else "", u.nome if u else "", c.emesso_at)


@router.get("/mie")
def miei_certificati(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """I miei attestati, con quanto serve a riconoscerli nello storico (corso, modalita', data, durata)."""
    rows = (db.query(Certificato, Iscrizione).join(Iscrizione, Certificato.iscrizione_id == Iscrizione.id)
            .filter(Iscrizione.user_id == user.id).order_by(Certificato.emesso_at.desc()).all())
    out = []
    for c, i in rows:
        e = db.query(Edizione).filter(Edizione.id == i.edizione_id).first()
        corso = db.query(Corso).filter(Corso.id == e.corso_id).first() if e else None
        out.append({
            "id": str(c.id), "iscrizione_id": str(i.id), "codice_verifica": c.codice_verifica, "emesso_at": c.emesso_at,
            "corso_titolo": corso.titolo if corso else None, "modalita": e.modalita if e else None,
            "data_corso": e.data_inizio if e else None, "completato_at": i.completato_at,
            "durata_minuti": durata_effettiva(e, corso) if e else None, "nome_file": _nome_file(db, c, i),
        })
    return out

@router.get("/{certificato_id}/pdf")
def scarica_pdf(certificato_id: str, inline: bool = False, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """`inline`: per vederlo nel browser invece di scaricarlo."""
    c = db.query(Certificato).filter(Certificato.id == certificato_id).first()
    if not c or not c.pdf_path:
        raise HTTPException(404)
    i = db.query(Iscrizione).filter(Iscrizione.id == c.iscrizione_id).first()
    if str(i.user_id) != str(user.id) and not user.ha_poteri_formazione:
        raise HTTPException(403)
    if not os.path.exists(c.pdf_path):
        raise HTTPException(404)
    return Response(cifratura.leggi_file(c.pdf_path), media_type="application/pdf",
                    headers={"Content-Disposition": f'{"inline" if inline else "attachment"}; filename="{_nome_file(db, c, i)}"', "Cache-Control": "private, no-store"})
