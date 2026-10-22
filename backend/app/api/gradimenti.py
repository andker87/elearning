import csv, io
from ..services.export import neutralizza
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import Any, Optional, Dict
from ..database import get_db
from ..models.test import Gradimento, GradimentoDocente, RispostaGradimento
from ..models.corso import Corso
from ..models.iscrizione import Iscrizione
from ..models.edizione import Edizione, EdizioneDocente
from ..models.user import User
from .deps import get_current_user, require_training_admin
from .questionari import questionario_per_corso

router = APIRouter(tags=["gradimenti"])

class GradimentoIn(BaseModel):
    voto_corso: int
    commento_corso: Optional[str] = None
    voti_docenti: Dict[str, int] = {}  # docente_id -> voto 1-5
    risposte: Dict[str, Any] = {}      # domanda_id -> risposta, per le domande aggiuntive del questionario

def _domande_del_corso(db: Session, iscrizione: Iscrizione):
    e = db.query(Edizione).filter(Edizione.id == iscrizione.edizione_id).first()
    corso = db.query(Corso).filter(Corso.id == e.corso_id).first() if e else None
    q = questionario_per_corso(db, corso)
    return list(q.domande) if q else []

@router.get("/api/iscrizioni/{iscrizione_id}/gradimento/modulo")
def modulo_gradimento(iscrizione_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Il modulo da compilare: domande aggiuntive del questionario del corso e docenti da valutare; se e' gia' stato inviato."""
    i = db.query(Iscrizione).filter(Iscrizione.id == iscrizione_id).first()
    if not i or str(i.user_id) != str(user.id):
        raise HTTPException(403, "Iscrizione non valida per l'utente corrente")
    docenti = db.query(EdizioneDocente).filter(EdizioneDocente.edizione_id == i.edizione_id).all()
    nomi = {u.id: u.full_name for u in db.query(User).filter(User.id.in_([d.user_id for d in docenti])).all()} if docenti else {}
    return {
        "gia_inviato": db.query(Gradimento).filter(Gradimento.iscrizione_id == i.id).first() is not None,
        "docenti": [{"id": str(d.user_id), "nome": nomi.get(d.user_id)} for d in docenti],
        "domande": [{"id": str(d.id), "testo": d.testo, "tipo": d.tipo, "opzioni": d.opzioni or [], "obbligatoria": d.obbligatoria} for d in _domande_del_corso(db, i)],
    }

def _valida_risposte(domande, risposte: Dict[str, Any]) -> list:
    """Controlla le risposte alle domande aggiuntive e restituisce le righe da salvare."""
    per_id = {str(d.id): d for d in domande}
    sconosciute = [k for k in risposte if k not in per_id]
    if sconosciute:
        raise HTTPException(400, "Risposta a una domanda che non fa parte del questionario")
    righe = []
    for d in domande:
        v = risposte.get(str(d.id))
        vuota = v is None or (isinstance(v, str) and not v.strip())
        if vuota:
            if d.obbligatoria:
                raise HTTPException(400, f"Rispondi alla domanda «{d.testo}»")
            continue
        num, testo = None, None
        if d.tipo == "stelle":
            if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 5:
                raise HTTPException(400, f"«{d.testo}»: scegli da 1 a 5 stelle")
            num = v
        elif d.tipo == "si_no":
            if v not in ("si", "no"):
                raise HTTPException(400, f"«{d.testo}»: rispondi sì o no")
            testo = v
        elif d.tipo == "scelta":
            if not isinstance(v, str) or v not in (d.opzioni or []):
                raise HTTPException(400, f"«{d.testo}»: scegli una delle opzioni")
            testo = v
        else:
            if not isinstance(v, str) or len(v.strip()) > 2000:
                raise HTTPException(400, f"«{d.testo}»: risposta troppo lunga (massimo 2000 caratteri)")
            testo = v.strip()
        righe.append(RispostaGradimento(domanda_id=d.id, testo_domanda=d.testo, tipo=d.tipo, valore_num=num, valore_testo=testo))
    return righe

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
            raise HTTPException(400, "Docente non associato a questa sessione")
        if voto < 1 or voto > 5:
            raise HTTPException(400, "Il voto per il docente deve essere tra 1 e 5")

    righe = _valida_risposte(_domande_del_corso(db, i), data.risposte)
    g = Gradimento(iscrizione_id=iscrizione_id, voto_corso=data.voto_corso, commento_corso=data.commento_corso)
    try:
        db.add(g); db.flush()                         # e' qui che il vincolo del database ferma un doppio invio in parallelo
        for r in righe:
            r.gradimento_id = g.id
            db.add(r)
        for docente_id, voto in data.voti_docenti.items():
            db.add(GradimentoDocente(gradimento_id=g.id, docente_id=docente_id, voto=voto))
        db.commit()
    except IntegrityError as err:  # due invii in parallelo: il vincolo del database lascia passare il primo
        db.rollback()
        raise HTTPException(400, "Gradimento già inviato per questa iscrizione") from err
    return {"ok": True}

@router.get("/api/edizioni/{edizione_id}/gradimenti")
def list_gradimenti(edizione_id: str, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    """Vista aggregata e anonima: mai il nome di chi ha risposto - solo
    medie/distribuzioni e i commenti liberi, spaiati da chi li ha scritti."""
    rows = (db.query(Gradimento).options(joinedload(Gradimento.voti_docenti), joinedload(Gradimento.risposte))
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
    nomi = {str(u.id): u for u in db.query(User).filter(User.id.in_(list(per_docente))).all()} if per_docente else {}
    for docente_id, voti in per_docente.items():
        d = nomi.get(docente_id)
        docenti_out.append({"docente_id": docente_id, "docente_nome": d.full_name if d else None,
                             "voto_medio": round(sum(voti) / len(voti), 2), "n_voti": len(voti)})

    # Domande aggiuntive: raggruppate per testo (quello conservato al momento della risposta)
    gruppi: Dict[tuple, list] = {}
    for g in rows:
        for r in g.risposte:
            gruppi.setdefault((r.testo_domanda, r.tipo), []).append(r)
    domande_out = []
    for (testo, tipo), lista in gruppi.items():
        voce = {"testo": testo, "tipo": tipo, "n_risposte": len(lista)}
        if tipo == "stelle":
            voce["media"] = round(sum(r.valore_num for r in lista) / len(lista), 2)
        elif tipo in ("si_no", "scelta"):
            conteggi: Dict[str, int] = {}
            for r in lista:
                conteggi[r.valore_testo] = conteggi.get(r.valore_testo, 0) + 1
            voce["conteggi"] = conteggi
        else:
            voce["testi"] = [r.valore_testo for r in lista]
        domande_out.append(voce)
    return {"n_risposte": n, "voto_corso_medio": voto_corso_medio, "commenti": commenti, "docenti": docenti_out, "domande": domande_out}

@router.get("/api/edizioni/{edizione_id}/report/gradimenti.csv")
def report_gradimenti_csv(edizione_id: str, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    docenti_rows = db.query(EdizioneDocente).filter(EdizioneDocente.edizione_id == edizione_id).all()
    utenti = {str(u.id): u for u in db.query(User).filter(User.id.in_([d.user_id for d in docenti_rows])).all()} if docenti_rows else {}
    docenti = [(str(d.user_id), utenti.get(str(d.user_id))) for d in docenti_rows]

    rows = (db.query(Gradimento).options(joinedload(Gradimento.voti_docenti), joinedload(Gradimento.risposte))
            .join(Iscrizione, Gradimento.iscrizione_id == Iscrizione.id)
            .filter(Iscrizione.edizione_id == edizione_id).all())
    aggiuntive = list(dict.fromkeys(r.testo_domanda for g in rows for r in g.risposte))      # una colonna per domanda, nell'ordine in cui compaiono

    buf = io.StringIO()
    w = csv.writer(buf)
    header = ["Voto corso", "Commento corso"] + [neutralizza(f"Voto docente: {u.full_name if u else did}") for did, u in docenti] + [neutralizza(t) for t in aggiuntive]
    w.writerow(header)
    for g in rows:
        voti_per_docente = {str(vd.docente_id): vd.voto for vd in g.voti_docenti}
        per_testo = {r.testo_domanda: (r.valore_num if r.valore_num is not None else neutralizza(r.valore_testo or "")) for r in g.risposte}
        riga = [g.voto_corso, neutralizza(g.commento_corso or "")] + [voti_per_docente.get(did, "") for did, _ in docenti] + [per_testo.get(t, "") for t in aggiuntive]
        w.writerow(riga)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                              headers={"Content-Disposition": f"attachment; filename=gradimenti_{edizione_id}.csv"})
