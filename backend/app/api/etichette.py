from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.etichetta import CorsoEtichetta, Etichetta, EtichettaFamiglia
from ..services import audit as audit_svc
from .deps import get_current_user, require_training_admin

router = APIRouter(prefix="/api/etichette", tags=["etichette"])


def _famiglie(db: Session, con_archiviate: bool = True):
    uso = dict(db.query(CorsoEtichetta.etichetta_id, func.count(CorsoEtichetta.id)).group_by(CorsoEtichetta.etichetta_id).all())
    q = db.query(EtichettaFamiglia)
    if not con_archiviate:
        q = q.filter(EtichettaFamiglia.archiviata == False)  # noqa: E712
    out = []
    for f in q.order_by(EtichettaFamiglia.ordine, EtichettaFamiglia.nome).all():
        valori = [e for e in f.etichette if con_archiviate or not e.archiviata]
        out.append({"id": str(f.id), "nome": f.nome, "descrizione": f.descrizione, "scelta_multipla": f.scelta_multipla,
                    "obbligatoria": f.obbligatoria, "ordine": f.ordine, "archiviata": f.archiviata,
                    "etichette": [{"id": str(e.id), "nome": e.nome, "ordine": e.ordine, "esclusiva": e.esclusiva, "archiviata": e.archiviata,
                                   "corsi": uso.get(e.id, 0)} for e in sorted(valori, key=lambda e: (e.archiviata, e.ordine, e.nome.lower()))]})
    return out


@router.get("")
def elenco(con_archiviate: bool = False, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _famiglie(db, con_archiviate)


class FamigliaIn(BaseModel):
    nome: str
    descrizione: Optional[str] = None
    scelta_multipla: bool = True
    obbligatoria: bool = False
    ordine: Optional[int] = None
    archiviata: bool = False


def _salva(db, oggetto_descr):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, f"Esiste già {oggetto_descr} con questo nome")


@router.post("/famiglie")
def crea_famiglia(data: FamigliaIn, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    nome = " ".join(data.nome.split())
    if not nome:
        raise HTTPException(400, "Il nome è obbligatorio")
    if db.query(EtichettaFamiglia).filter(func.lower(EtichettaFamiglia.nome) == nome.lower()).first():
        raise HTTPException(400, f"Esiste già una famiglia «{nome}»")
    ordine = data.ordine if data.ordine is not None else (db.query(func.max(EtichettaFamiglia.ordine)).scalar() or 0) + 1
    f = EtichettaFamiglia(nome=nome, descrizione=data.descrizione, scelta_multipla=data.scelta_multipla, obbligatoria=data.obbligatoria, ordine=ordine)
    db.add(f)
    audit_svc.log_from_request(db, request, user, "CREATE", entity_type="etichetta_famiglia", entity_name=nome)
    _salva(db, "una famiglia")
    return {"id": str(f.id)}


@router.put("/famiglie/{famiglia_id}")
def modifica_famiglia(famiglia_id: str, data: FamigliaIn, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    f = db.query(EtichettaFamiglia).filter(EtichettaFamiglia.id == famiglia_id).first()
    if not f: raise HTTPException(404)
    nome = " ".join(data.nome.split())
    if not nome:
        raise HTTPException(400, "Il nome è obbligatorio")
    if db.query(EtichettaFamiglia).filter(func.lower(EtichettaFamiglia.nome) == nome.lower(), EtichettaFamiglia.id != f.id).first():
        raise HTTPException(400, f"Esiste già una famiglia «{nome}»")
    if not data.scelta_multipla and f.scelta_multipla:
        troppe = (db.query(CorsoEtichetta.corso_id).join(Etichetta, Etichetta.id == CorsoEtichetta.etichetta_id)
                  .filter(Etichetta.famiglia_id == f.id).group_by(CorsoEtichetta.corso_id).having(func.count() > 1).count())
        if troppe:
            raise HTTPException(400, f"{troppe} corsi hanno più etichette di «{f.nome}»: sistemali prima di renderla a scelta singola")
    f.nome, f.descrizione, f.scelta_multipla, f.obbligatoria, f.archiviata = nome, data.descrizione, data.scelta_multipla, data.obbligatoria, data.archiviata
    if data.ordine is not None:
        f.ordine = data.ordine
    audit_svc.log_from_request(db, request, user, "UPDATE", entity_type="etichetta_famiglia", entity_name=nome)
    _salva(db, "una famiglia")
    return {"ok": True}


@router.delete("/famiglie/{famiglia_id}")
def elimina_famiglia(famiglia_id: str, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    f = db.query(EtichettaFamiglia).filter(EtichettaFamiglia.id == famiglia_id).first()
    if not f: raise HTTPException(404)
    in_uso = db.query(CorsoEtichetta).join(Etichetta, Etichetta.id == CorsoEtichetta.etichetta_id).filter(Etichetta.famiglia_id == f.id).count()
    if in_uso:
        raise HTTPException(400, "La famiglia ha etichette assegnate ai corsi: archiviala invece di eliminarla")
    db.query(Etichetta).filter(Etichetta.famiglia_id == f.id).delete()
    audit_svc.log_from_request(db, request, user, "DELETE", entity_type="etichetta_famiglia", entity_name=f.nome)
    db.delete(f)
    db.commit()
    return {"ok": True}


class EtichettaIn(BaseModel):
    nome: str
    esclusiva: bool = False
    archiviata: bool = False
    ordine: Optional[int] = None


@router.post("/famiglie/{famiglia_id}/etichette")
def crea_etichetta(famiglia_id: str, data: EtichettaIn, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    f = db.query(EtichettaFamiglia).filter(EtichettaFamiglia.id == famiglia_id).first()
    if not f: raise HTTPException(404)
    nome = " ".join(data.nome.split())
    if not nome:
        raise HTTPException(400, "Il nome è obbligatorio")
    if db.query(Etichetta).filter(Etichetta.famiglia_id == f.id, func.lower(Etichetta.nome) == nome.lower()).first():
        raise HTTPException(400, f"«{nome}» esiste già in {f.nome}")
    ordine = data.ordine if data.ordine is not None else (db.query(func.max(Etichetta.ordine)).filter(Etichetta.famiglia_id == f.id).scalar() or 0) + 1
    e = Etichetta(famiglia_id=f.id, nome=nome, esclusiva=data.esclusiva, ordine=ordine)
    db.add(e)
    audit_svc.log_from_request(db, request, user, "CREATE", entity_type="etichetta", entity_name=f"{f.nome}: {nome}")
    _salva(db, "un'etichetta")
    return {"id": str(e.id)}


@router.put("/{etichetta_id}")
def modifica_etichetta(etichetta_id: str, data: EtichettaIn, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    e = db.query(Etichetta).filter(Etichetta.id == etichetta_id).first()
    if not e: raise HTTPException(404)
    nome = " ".join(data.nome.split())
    if not nome:
        raise HTTPException(400, "Il nome è obbligatorio")
    if db.query(Etichetta).filter(Etichetta.famiglia_id == e.famiglia_id, func.lower(Etichetta.nome) == nome.lower(), Etichetta.id != e.id).first():
        raise HTTPException(400, f"«{nome}» esiste già in questa famiglia: usa «Unisci» per fonderle")
    vecchio = e.nome
    e.nome, e.esclusiva, e.archiviata = nome, data.esclusiva, data.archiviata
    if data.ordine is not None:
        e.ordine = data.ordine
    audit_svc.log_from_request(db, request, user, "UPDATE", entity_type="etichetta", entity_name=f"{e.famiglia.nome}: {nome}",
                                detail=f"rinominata da «{vecchio}»" if vecchio != nome else None)
    _salva(db, "un'etichetta")
    return {"ok": True}


@router.delete("/{etichetta_id}")
def elimina_etichetta(etichetta_id: str, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    e = db.query(Etichetta).filter(Etichetta.id == etichetta_id).first()
    if not e: raise HTTPException(404)
    if db.query(CorsoEtichetta).filter(CorsoEtichetta.etichetta_id == e.id).count():
        raise HTTPException(400, "L'etichetta è assegnata a dei corsi: archiviala (resta nelle estrazioni passate) o uniscila a un'altra")
    audit_svc.log_from_request(db, request, user, "DELETE", entity_type="etichetta", entity_name=f"{e.famiglia.nome}: {e.nome}")
    db.delete(e)
    db.commit()
    return {"ok": True}


class UnisciIn(BaseModel):
    in_etichetta_id: str


@router.post("/{etichetta_id}/unisci")
def unisci_etichette(etichetta_id: str, data: UnisciIn, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    """Sposta i corsi su un'altra etichetta della stessa famiglia ed elimina questa (doppioni, errori di grafia)."""
    da = db.query(Etichetta).filter(Etichetta.id == etichetta_id).first()
    a = db.query(Etichetta).filter(Etichetta.id == data.in_etichetta_id).first()
    if not da or not a: raise HTTPException(404)
    if da.id == a.id or da.famiglia_id != a.famiglia_id:
        raise HTTPException(400, "Si uniscono solo due etichette diverse della stessa famiglia")
    gia = {c for (c,) in db.query(CorsoEtichetta.corso_id).filter(CorsoEtichetta.etichetta_id == a.id).all()}
    spostati = 0
    for ce in db.query(CorsoEtichetta).filter(CorsoEtichetta.etichetta_id == da.id).all():
        if ce.corso_id in gia:
            db.delete(ce)
        else:
            ce.etichetta_id = a.id
            spostati += 1
    audit_svc.log_from_request(db, request, user, "UPDATE", entity_type="etichetta", entity_name=f"{a.famiglia.nome}: {a.nome}",
                                detail=f"unita «{da.nome}» ({spostati} corsi spostati)")
    db.flush()
    db.delete(da)
    db.commit()
    return {"spostati": spostati}
