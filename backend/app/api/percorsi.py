from fastapi import APIRouter, Depends, HTTPException, Request
from ..services import audit as audit_svc
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
from ..database import get_db
from ..models.percorso import (
    PercorsoFormativo, PercorsoStep, PercorsoStepPrerequisito, PercorsoAssegnazione,
    MotivoObbligo, TriggerAssegnazione,
)
from ..models.group import UserGroup
from ..models.user import User
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.edizione import Edizione
from .deps import require_training_admin, get_current_user

router = APIRouter(prefix="/api/percorsi", tags=["percorsi"])

class StepIn(BaseModel):
    corso_id: str
    ordine: int = 0
    richiede_step_ordini: List[int] = []  # prerequisiti espressi per ordine, risolti alla creazione

class PercorsoIn(BaseModel):
    nome: str
    descrizione: Optional[str] = None
    # Non piu' usati (l'obbligo e' del corso: etichette, famiglia Obbligo). Accettati e ignorati in
    # modifica per compatibilita'; alla creazione resta il valore predefinito.
    motivo: MotivoObbligo = MotivoObbligo.policy_interna
    motivo_nota: Optional[str] = None
    trigger_tipo: TriggerAssegnazione = TriggerAssegnazione.manuale
    trigger_gruppo_id: Optional[str] = None       # ufficio (e sottouffici)
    trigger_mansione_id: Optional[str] = None
    steps: List[StepIn] = []

def _serialize(p: PercorsoFormativo):
    return {
        "id": str(p.id), "nome": p.nome, "descrizione": p.descrizione,
        "motivo": p.motivo, "motivo_nota": p.motivo_nota,
        "trigger_tipo": p.trigger_tipo,
        "trigger_gruppo_id": str(p.trigger_gruppo_id) if p.trigger_gruppo_id else None,
        "trigger_mansione_id": str(p.trigger_mansione_id) if p.trigger_mansione_id else None,
        "is_active": p.is_active,
        "steps": [{"id": str(s.id), "corso_id": str(s.corso_id), "ordine": s.ordine,
                   "richiede_step_ids": [str(pr.richiede_step_id) for pr in s.prerequisiti]}
                  for s in p.steps],
    }

@router.get("")
def list_percorsi(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return [_serialize(p) for p in db.query(PercorsoFormativo).options(joinedload(PercorsoFormativo.steps)).all()]

@router.post("")
def create_percorso(data: PercorsoIn, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    p = PercorsoFormativo(nome=data.nome, descrizione=data.descrizione, motivo=data.motivo,
                           motivo_nota=data.motivo_nota, trigger_tipo=data.trigger_tipo,
                           trigger_gruppo_id=data.trigger_gruppo_id, trigger_mansione_id=data.trigger_mansione_id)
    db.add(p); db.flush()

    step_by_ordine = {}
    for s in data.steps:
        step = PercorsoStep(percorso_id=p.id, corso_id=s.corso_id, ordine=s.ordine)
        db.add(step); db.flush()
        step_by_ordine[s.ordine] = step
    for s in data.steps:
        step = step_by_ordine[s.ordine]
        for req_ordine in s.richiede_step_ordini:
            richiesto = step_by_ordine.get(req_ordine)
            if richiesto:
                db.add(PercorsoStepPrerequisito(step_id=step.id, richiede_step_id=richiesto.id))

    audit_svc.log_from_request(db, request, user, "CREATE", entity_type="percorso", entity_id=str(p.id), entity_name=p.nome)
    db.commit(); db.refresh(p)

    from ..services.percorsi_sync import sincronizza_assegnazioni
    sincronizza_assegnazioni(db, percorso_id=str(p.id))
    db.commit()
    return _serialize(p)

@router.post("/sincronizza")
def sincronizza_percorsi(request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    """Rivaluta i trigger automatici (ingresso in azienda / gruppo) su tutti i
    percorsi e crea le assegnazioni mancanti - utile dopo aver modificato gruppi
    o date di ingresso, o dopo aver cambiato il trigger di un percorso."""
    from ..services.percorsi_sync import sincronizza_assegnazioni
    creati = sincronizza_assegnazioni(db)
    audit_svc.log_from_request(db, request, user, "SYNC", entity_type="percorso", entity_name="Sincronizzazione trigger percorsi",
                                detail=f"nuove assegnazioni: {creati}")
    db.commit()
    return {"ok": True, "nuove_assegnazioni": creati}

@router.post("/{percorso_id}/assegna")
def assegna_percorso(percorso_id: str, user_ids: List[str], request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    p = db.query(PercorsoFormativo).filter(PercorsoFormativo.id == percorso_id).first()
    if not p: raise HTTPException(404)
    creati = []
    for uid in user_ids:
        esiste = db.query(PercorsoAssegnazione).filter(
            PercorsoAssegnazione.percorso_id == percorso_id, PercorsoAssegnazione.user_id == uid).first()
        if esiste: continue
        db.add(PercorsoAssegnazione(percorso_id=percorso_id, user_id=uid))
        creati.append(uid)
    audit_svc.log_from_request(db, request, user, "ASSIGN", entity_type="percorso", entity_id=percorso_id, entity_name=p.nome,
                                detail=f"assegnato a {len(creati)} utenti: " + ", ".join(audit_svc.nome_utente(db, u) for u in creati[:10])
                                       + ("..." if len(creati) > 10 else ""))
    db.commit()
    return {"ok": True, "assegnati": creati}

def _corso_completato_da(db: Session, user_id: str, corso_id: str) -> bool:
    """Un Corso è completato per l'utente se esiste almeno un'iscrizione a
    un'edizione di quel corso in stato 'completato' - indipendentemente da
    quale percorso l'abbia richiesto (stato condiviso, non duplicato)."""
    return db.query(Iscrizione).join(Edizione, Iscrizione.edizione_id == Edizione.id).filter(
        Iscrizione.user_id == user_id, Edizione.corso_id == corso_id,
        Iscrizione.stato == StatoIscrizione.completato,
    ).first() is not None

def _calcola_stato_steps(db: Session, p: PercorsoFormativo, user_id: str):
    from ..models.corso import Corso
    stato_steps = []
    completati_ids = set()
    for s in sorted(p.steps, key=lambda x: x.ordine):
        corso = db.query(Corso).filter(Corso.id == s.corso_id).first()
        completato = _corso_completato_da(db, user_id, str(s.corso_id))
        sbloccato = all(str(pr.richiede_step_id) in completati_ids for pr in s.prerequisiti)
        if completato: completati_ids.add(str(s.id))
        stato_steps.append({"step_id": str(s.id), "corso_id": str(s.corso_id),
                             "corso_titolo": corso.titolo if corso else None, "ordine": s.ordine,
                             "completato": completato, "sbloccato": sbloccato})
    return stato_steps

@router.get("/{percorso_id}/stato/{user_id}")
def stato_percorso_utente(percorso_id: str, user_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = db.query(PercorsoFormativo).options(joinedload(PercorsoFormativo.steps)).filter(PercorsoFormativo.id == percorso_id).first()
    if not p: raise HTTPException(404)
    return {"percorso_id": percorso_id, "user_id": user_id, "steps": _calcola_stato_steps(db, p, user_id)}

@router.get("/mie")
def miei_percorsi(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Percorsi assegnati all'utente corrente, con lo stato di avanzamento di
    ogni step - usato dalla dashboard 'I miei corsi'."""
    assegnazioni = db.query(PercorsoAssegnazione).filter(PercorsoAssegnazione.user_id == user.id).all()
    out = []
    for a in assegnazioni:
        p = db.query(PercorsoFormativo).options(joinedload(PercorsoFormativo.steps)).filter(PercorsoFormativo.id == a.percorso_id).first()
        if not p: continue
        steps = _calcola_stato_steps(db, p, str(user.id))
        completato = all(s["completato"] for s in steps) if steps else False
        if completato and not a.completato:
            a.completato = True
            a.completato_il = datetime.now(timezone.utc)
            db.commit()
        out.append({"assegnazione_id": str(a.id), "percorso_id": str(p.id), "nome": p.nome,
                    "completato": completato, "steps": steps})
    return out

# NOTA: le rotte con un solo segmento dinamico (/{percorso_id}) vanno registrate
# DOPO tutte le rotte letterali a un segmento ("/mie", "/sincronizza") - altrimenti
# FastAPI le farebbe collidere (es. "/percorsi/mie" interpretato come percorso_id="mie").

@router.get("/{percorso_id}")
def get_percorso(percorso_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = db.query(PercorsoFormativo).options(joinedload(PercorsoFormativo.steps)).filter(PercorsoFormativo.id == percorso_id).first()
    if not p: raise HTTPException(404)
    return _serialize(p)

@router.put("/{percorso_id}")
def update_percorso(percorso_id: str, data: PercorsoIn, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    p = db.query(PercorsoFormativo).filter(PercorsoFormativo.id == percorso_id).first()
    if not p: raise HTTPException(404)
    p.nome = data.nome
    p.descrizione = data.descrizione
    p.trigger_tipo = data.trigger_tipo
    p.trigger_gruppo_id = data.trigger_gruppo_id
    p.trigger_mansione_id = data.trigger_mansione_id
    audit_svc.log_from_request(db, request, user, "UPDATE", entity_type="percorso", entity_id=str(p.id), entity_name=p.nome)

    # Sostituzione completa degli step: l'autoring è admin-only e poco frequente,
    # più semplice che fare un diff fine (stesso approccio usato per i Test).
    vecchi_step_ids = [s.id for s in db.query(PercorsoStep).filter(PercorsoStep.percorso_id == p.id).all()]
    db.query(PercorsoStepPrerequisito).filter(PercorsoStepPrerequisito.step_id.in_(vecchi_step_ids)).delete(synchronize_session=False)
    db.query(PercorsoStep).filter(PercorsoStep.percorso_id == p.id).delete(synchronize_session=False)
    db.flush()

    step_by_ordine = {}
    for s in data.steps:
        step = PercorsoStep(percorso_id=p.id, corso_id=s.corso_id, ordine=s.ordine)
        db.add(step); db.flush()
        step_by_ordine[s.ordine] = step
    for s in data.steps:
        step = step_by_ordine[s.ordine]
        for req_ordine in s.richiede_step_ordini:
            richiesto = step_by_ordine.get(req_ordine)
            if richiesto:
                db.add(PercorsoStepPrerequisito(step_id=step.id, richiede_step_id=richiesto.id))

    db.commit()

    from ..services.percorsi_sync import sincronizza_assegnazioni
    sincronizza_assegnazioni(db, percorso_id=str(p.id))
    db.commit(); db.refresh(p)
    return _serialize(p)
