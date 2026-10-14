import csv, io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import Optional, Dict
from ..database import get_db
from ..models.test import Gradimento, GradimentoDocente
from ..models.iscrizione import Iscrizione
from ..models.edizione import Edizione, EdizioneDocente
from ..models.user import User
from .deps import get_current_user, require_training_admin

router = APIRouter(tags=["gradimenti"])

class GradimentoIn(BaseModel):
    voto_corso: int
    commento_corso: Optional[str] = None
    voti_docenti: Dict[str, int] = {}  # docente_id -> voto 1-5

@router.post("/api/iscrizioni/{iscrizione_id}/gradimento")
def crea_gradimento(iscrizione_id: str, data: GradimentoIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    i = db.query(Iscrizione).filter(Iscrizione.id == iscrizione_id).first()
    if not i or str(i.user_id) != str(user.id):
        raise HTTPException(403, "Iscrizione non valida per l'utente corrente")
    if data.voto_corso < 1 or data.voto_corso > 5:
        raise HTTPException(400, "Il voto deve essere tra 1 e 5")
    esiste = db.query(Gradimento).filter(Gradimento.iscrizione_id == iscrizione_id).first()
    if esiste:
        raise HTTPException(400, "Gradimento già inviato per questa iscrizione")

    docenti_edizione = {str(d.user_id) for d in db.query(EdizioneDocente).filter(EdizioneDocente.edizione_id == i.edizione_id).all()}
    for docente_id, voto in data.voti_docenti.items():
        if docente_id not in docenti_edizione:
            raise HTTPException(400, "Docente non associato a questa edizione")
        if voto < 1 or voto > 5:
            raise HTTPException(400, "Il voto per il docente deve essere tra 1 e 5")

    g = Gradimento(iscrizione_id=iscrizione_id, voto_corso=data.voto_corso, commento_corso=data.commento_corso)
    db.add(g); db.flush()
    for docente_id, voto in data.voti_docenti.items():
        db.add(GradimentoDocente(gradimento_id=g.id, docente_id=docente_id, voto=voto))
    db.commit()
    return {"ok": True}

@router.get("/api/edizioni/{edizione_id}/gradimenti")
def list_gradimenti(edizione_id: str, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    """Vista aggregata e anonima: mai il nome di chi ha risposto - solo
    medie/distribuzioni e i commenti liberi, spaiati da chi li ha scritti."""
    rows = (db.query(Gradimento).options(joinedload(Gradimento.voti_docenti))
            .join(Iscrizione, Gradimento.iscrizione_id == Iscrizione.id)
            .filter(Iscrizione.edizione_id == edizione_id).all())

    n = len(rows)
    voto_corso_medio = round(sum(g.voto_corso for g in rows) / n, 2) if n else None
    commenti = [g.commento_corso for g in rows if g.commento_corso]

    per_docente: Dict[str, list] = {}
    for g in rows:
        for vd in g.voti_docenti:
            per_docente.setdefault(str(vd.docente_id), []).append(vd.voto)
    docenti_out = []
    for docente_id, voti in per_docente.items():
        d = db.query(User).filter(User.id == docente_id).first()
        docenti_out.append({"docente_id": docente_id, "docente_nome": d.full_name if d else None,
                             "voto_medio": round(sum(voti) / len(voti), 2), "n_voti": len(voti)})

    return {"n_risposte": n, "voto_corso_medio": voto_corso_medio, "commenti": commenti, "docenti": docenti_out}

@router.get("/api/edizioni/{edizione_id}/report/gradimenti.csv")
def report_gradimenti_csv(edizione_id: str, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    edizione = db.query(Edizione).filter(Edizione.id == edizione_id).first()
    docenti_rows = db.query(EdizioneDocente).filter(EdizioneDocente.edizione_id == edizione_id).all()
    docenti = [(str(d.user_id), db.query(User).filter(User.id == d.user_id).first()) for d in docenti_rows]

    rows = (db.query(Gradimento).options(joinedload(Gradimento.voti_docenti))
            .join(Iscrizione, Gradimento.iscrizione_id == Iscrizione.id)
            .filter(Iscrizione.edizione_id == edizione_id).all())

    buf = io.StringIO()
    w = csv.writer(buf)
    header = ["Voto corso", "Commento corso"] + [f"Voto docente: {u.full_name if u else did}" for did, u in docenti]
    w.writerow(header)
    for g in rows:
        voti_per_docente = {str(vd.docente_id): vd.voto for vd in g.voti_docenti}
        riga = [g.voto_corso, g.commento_corso or ""] + [voti_per_docente.get(did, "") for did, _ in docenti]
        w.writerow(riga)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                              headers={"Content-Disposition": f"attachment; filename=gradimenti_{edizione_id}.csv"})
