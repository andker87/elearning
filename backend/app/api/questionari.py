"""Questionari di gradimento: la Formazione decide quali domande aggiuntive fare, oltre a quelle fisse
(voto complessivo, commento, voto ai docenti)."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models.corso import Corso
from ..models.questionario import DomandaGradimento, QuestionarioGradimento, TIPI_DOMANDA
from ..services import audit as audit_svc
from .deps import require_training_admin

router = APIRouter(prefix="/api/questionari", tags=["questionari"])

MAX_DOMANDE = 20
MAX_OPZIONI = 10


class DomandaIn(BaseModel):
    testo: str
    tipo: str
    opzioni: List[str] = []
    obbligatoria: bool = False

    @field_validator("testo")
    @classmethod
    def _testo(cls, v):
        v = (v or "").strip()
        if not 1 <= len(v) <= 300:
            raise ValueError("Il testo di ogni domanda va da 1 a 300 caratteri")
        return v

    @field_validator("tipo")
    @classmethod
    def _tipo(cls, v):
        if v not in TIPI_DOMANDA:
            raise ValueError("Tipo di domanda non valido")
        return v


class QuestionarioIn(BaseModel):
    nome: str
    is_default: bool = False
    domande: List[DomandaIn] = []

    @field_validator("nome")
    @classmethod
    def _nome(cls, v):
        v = (v or "").strip()
        if not 1 <= len(v) <= 100:
            raise ValueError("Il nome del questionario va da 1 a 100 caratteri")
        return v


def _pulisci(domande: List[DomandaIn]) -> List[dict]:
    if len(domande) > MAX_DOMANDE:
        raise HTTPException(400, f"Al massimo {MAX_DOMANDE} domande per questionario")
    out = []
    for d in domande:
        opzioni = []
        if d.tipo == "scelta":
            opzioni = [o.strip() for o in d.opzioni if o and o.strip()]
            if len(set(opzioni)) != len(opzioni):
                raise HTTPException(400, f"«{d.testo}»: le opzioni devono essere diverse tra loro")
            if not 2 <= len(opzioni) <= MAX_OPZIONI or any(len(o) > 100 for o in opzioni):
                raise HTTPException(400, f"«{d.testo}»: servono da 2 a {MAX_OPZIONI} opzioni (fino a 100 caratteri ciascuna)")
        out.append({"testo": d.testo, "tipo": d.tipo, "opzioni": opzioni or None, "obbligatoria": d.obbligatoria})
    return out


def _serialize(q: QuestionarioGradimento, db: Session) -> dict:
    n_corsi = db.query(Corso).filter(Corso.questionario_gradimento_id == q.id).count()
    return {"id": str(q.id), "nome": q.nome, "is_default": q.is_default, "n_corsi": n_corsi,
            "domande": [{"id": str(d.id), "testo": d.testo, "tipo": d.tipo, "opzioni": d.opzioni or [], "obbligatoria": d.obbligatoria} for d in q.domande]}


def questionario_per_corso(db: Session, corso) -> Optional[QuestionarioGradimento]:
    """Quello scelto dal corso, altrimenti il predefinito, altrimenti nessuno (restano le sole domande fisse)."""
    if corso is not None and corso.questionario_gradimento_id:
        q = db.query(QuestionarioGradimento).options(joinedload(QuestionarioGradimento.domande)).filter(QuestionarioGradimento.id == corso.questionario_gradimento_id).first()
        if q:
            return q
    return db.query(QuestionarioGradimento).options(joinedload(QuestionarioGradimento.domande)).filter(QuestionarioGradimento.is_default == True).first()  # noqa: E712


def _controlla_nome(db: Session, nome: str, escludi_id=None):
    q = db.query(QuestionarioGradimento).filter(QuestionarioGradimento.nome == nome)
    if escludi_id is not None:
        q = q.filter(QuestionarioGradimento.id != escludi_id)
    if q.first():
        raise HTTPException(400, "Esiste già un questionario con questo nome")


def _imposta(db: Session, q: QuestionarioGradimento, data: QuestionarioIn):
    domande = _pulisci(data.domande)
    q.nome = data.nome
    if data.is_default:        # uno solo e' il predefinito
        db.query(QuestionarioGradimento).filter(QuestionarioGradimento.id != q.id).update({"is_default": False})
    q.is_default = data.is_default
    q.domande.clear()
    db.flush()
    for i, d in enumerate(domande):
        q.domande.append(DomandaGradimento(ordine=i, **d))


@router.get("")
def elenco(db: Session = Depends(get_db), user=Depends(require_training_admin)):
    qs = db.query(QuestionarioGradimento).options(joinedload(QuestionarioGradimento.domande)).order_by(QuestionarioGradimento.nome).all()
    return [_serialize(q, db) for q in qs]


@router.post("")
def crea(data: QuestionarioIn, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    _controlla_nome(db, data.nome)
    _pulisci(data.domande)          # errori di validazione prima di scrivere
    try:
        q = QuestionarioGradimento(nome=data.nome)
        db.add(q); db.flush()
        _imposta(db, q, data)
        audit_svc.log_from_request(db, request, user, "CREATE", entity_type="questionario", entity_id=str(q.id), entity_name=q.nome)
        db.commit()
    except IntegrityError as err:        # due salvataggi in parallelo con lo stesso nome: passano entrambi il controllo, il database ne ferma uno
        db.rollback()
        raise HTTPException(400, "Esiste già un questionario con questo nome") from err
    db.refresh(q)
    return _serialize(q, db)


@router.put("/{questionario_id}")
def modifica(questionario_id: str, data: QuestionarioIn, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    q = db.query(QuestionarioGradimento).options(joinedload(QuestionarioGradimento.domande)).filter(QuestionarioGradimento.id == questionario_id).first()
    if not q: raise HTTPException(404)
    _controlla_nome(db, data.nome, q.id)
    try:
        _imposta(db, q, data)
        audit_svc.log_from_request(db, request, user, "UPDATE", entity_type="questionario", entity_id=str(q.id), entity_name=q.nome)
        db.commit()
    except IntegrityError as err:
        db.rollback()
        raise HTTPException(400, "Esiste già un questionario con questo nome") from err
    db.refresh(q)
    return _serialize(q, db)


@router.delete("/{questionario_id}")
def elimina(questionario_id: str, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    q = db.query(QuestionarioGradimento).filter(QuestionarioGradimento.id == questionario_id).first()
    if not q: raise HTTPException(404)
    n = db.query(Corso).filter(Corso.questionario_gradimento_id == q.id).count()
    if n:
        raise HTTPException(409, f"Il questionario è scelto da {n} {'corso' if n == 1 else 'corsi'}: cambialo prima in quei corsi")
    nome = q.nome
    db.delete(q)
    audit_svc.log_from_request(db, request, user, "DELETE", entity_type="questionario", entity_id=questionario_id, entity_name=nome)
    db.commit()
    return {"ok": True}
