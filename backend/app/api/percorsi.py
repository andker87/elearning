from fastapi import APIRouter, Depends, HTTPException, Request
from ..services import audit as audit_svc
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime, timezone
from ..database import get_db
from ..models.percorso import (
    PercorsoFormativo, PercorsoStep, PercorsoStepPrerequisito, PercorsoAssegnazione,
    MotivoObbligo, TriggerAssegnazione, MODALITA_PERCORSO,
)
from ..models.group import UserGroup
from ..models.user import User
from ..services.gerarchia import sottoposti_di
from ..services.notifiche import _crea_se_assente
from ..services.percorsi_iscrizioni import avanza_e_invita, calcola_stato_steps, ha_cicli
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
    modalita: str = "libero"           # libero / sequenziale / propedeuticita
    steps: List[StepIn] = []

    @field_validator("modalita")
    @classmethod
    def _modalita(cls, v):
        if v not in MODALITA_PERCORSO:
            raise ValueError("Modalità del percorso non valida")
        return v

def _controlla_steps(data: PercorsoIn):
    """Un corso una volta sola, un ordine una volta sola, e con le propedeuticità nessun giro (A richiede B che richiede A)."""
    ordini = [s.ordine for s in data.steps]
    if len(set(ordini)) != len(ordini):
        raise HTTPException(400, "Due corsi hanno lo stesso numero d'ordine: dai a ogni corso un numero diverso")
    corsi = [s.corso_id for s in data.steps]
    if len(set(corsi)) != len(corsi):
        raise HTTPException(400, "Un corso compare più volte nel percorso")
    if data.modalita == "propedeuticita":
        for st in data.steps:
            if st.ordine in st.richiede_step_ordini:
                raise HTTPException(400, "Un corso non può richiedere se stesso")
        if ha_cicli({st.ordine: [r for r in st.richiede_step_ordini if r in ordini] for st in data.steps}):
            raise HTTPException(400, "Le propedeuticità si richiamano a vicenda: un corso non può richiedere, anche indirettamente, se stesso")

def _crea_steps(db: Session, p: PercorsoFormativo, data: PercorsoIn):
    step_by_ordine = {}
    for s in data.steps:
        step = PercorsoStep(percorso_id=p.id, corso_id=s.corso_id, ordine=s.ordine)
        db.add(step); db.flush()
        step_by_ordine[s.ordine] = step
    if data.modalita != "propedeuticita":
        return          # libero e sequenziale non hanno prerequisiti da scrivere: il sequenziale li ricava dall'ordine
    for s in data.steps:
        step = step_by_ordine[s.ordine]
        for req_ordine in s.richiede_step_ordini:
            richiesto = step_by_ordine.get(req_ordine)
            if richiesto:
                db.add(PercorsoStepPrerequisito(step_id=step.id, richiede_step_id=richiesto.id))

def _serialize(p: PercorsoFormativo, n_assegnati: Optional[int] = None):
    return {"n_assegnati": n_assegnati,
        "id": str(p.id), "nome": p.nome, "descrizione": p.descrizione,
        "motivo": p.motivo, "motivo_nota": p.motivo_nota,
        "trigger_tipo": p.trigger_tipo,
        "trigger_gruppo_id": str(p.trigger_gruppo_id) if p.trigger_gruppo_id else None,
        "trigger_mansione_id": str(p.trigger_mansione_id) if p.trigger_mansione_id else None,
        "is_active": p.is_active, "modalita": p.modalita,
        "steps": [{"id": str(s.id), "corso_id": str(s.corso_id), "ordine": s.ordine,
                   "richiede_step_ids": [str(pr.richiede_step_id) for pr in s.prerequisiti]}
                  for s in p.steps],
    }

@router.get("")
def list_percorsi(db: Session = Depends(get_db), user=Depends(get_current_user)):
    conteggi = dict(db.query(PercorsoAssegnazione.percorso_id, func.count(PercorsoAssegnazione.id)).group_by(PercorsoAssegnazione.percorso_id).all())
    return [_serialize(p, conteggi.get(p.id, 0)) for p in db.query(PercorsoFormativo).options(joinedload(PercorsoFormativo.steps)).order_by(PercorsoFormativo.nome).all()]

@router.post("")
def create_percorso(data: PercorsoIn, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    _controlla_steps(data)
    p = PercorsoFormativo(nome=data.nome, descrizione=data.descrizione, motivo=data.motivo, modalita=data.modalita,
                           motivo_nota=data.motivo_nota, trigger_tipo=data.trigger_tipo,
                           trigger_gruppo_id=data.trigger_gruppo_id, trigger_mansione_id=data.trigger_mansione_id)
    db.add(p); db.flush()
    _crea_steps(db, p, data)

    audit_svc.log_from_request(db, request, user, "CREATE", entity_type="percorso", entity_id=str(p.id), entity_name=p.nome)
    db.commit(); db.refresh(p)

    from ..services.percorsi_sync import sincronizza_assegnazioni
    sincronizza_assegnazioni(db, percorso_id=str(p.id))
    db.commit()
    avanza_e_invita(db, percorso_ids=[p.id])          # chi riceve il percorso in automatico viene iscritto ai corsi sbloccati
    db.refresh(p)
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
    avanzamento = avanza_e_invita(db)
    return {"ok": True, "nuove_assegnazioni": creati, "iscrizioni": avanzamento["iscritti"] + avanzamento["in_lista_attesa"],
            "in_attesa_sessione": avanzamento["in_attesa_sessione"]}

@router.post("/{percorso_id}/assegna")
def assegna_percorso(percorso_id: str, user_ids: List[str], request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    """Assegna il percorso alle persone indicate e le iscrive subito ai corsi gia' sbloccati (gli altri a mano a mano)."""
    p = db.query(PercorsoFormativo).filter(PercorsoFormativo.id == percorso_id).first()
    if not p: raise HTTPException(404)
    if not p.is_active:
        raise HTTPException(400, "Il percorso non è attivo")
    creati, saltati = [], []
    for uid in dict.fromkeys(user_ids):
        persona = db.query(User).filter(User.id == uid, User.is_active == True).first()  # noqa: E712
        if not persona:
            saltati.append({"user_id": uid, "motivo": "persona non trovata o non attiva"})
            continue
        esiste = db.query(PercorsoAssegnazione).filter(
            PercorsoAssegnazione.percorso_id == percorso_id, PercorsoAssegnazione.user_id == uid).first()
        if esiste:
            saltati.append({"user_id": uid, "motivo": "ha già il percorso"})
            continue
        db.add(PercorsoAssegnazione(percorso_id=percorso_id, user_id=uid))
        creati.append(uid)
        _crea_se_assente(db, uid, "percorso_assegnato", f"Ti è stato assegnato il percorso formativo «{p.nome}»: trovi i corsi in «I miei corsi».",
                         dedup_key=f"percorso_assegnato:{percorso_id}:{uid}", link="/miei-corsi")
    audit_svc.log_from_request(db, request, user, "ASSIGN", entity_type="percorso", entity_id=percorso_id, entity_name=p.nome,
                                detail=f"assegnato a {len(creati)} utenti: " + ", ".join(audit_svc.nome_utente(db, u) for u in creati[:10])
                                       + ("..." if len(creati) > 10 else ""))
    db.commit()
    avanzamento = avanza_e_invita(db, user_ids=creati) if creati else {"iscritti": 0, "in_lista_attesa": 0, "in_attesa_sessione": 0, "da_rifare": 0}
    return {"ok": True, "assegnati": creati, "saltati": saltati, "iscrizioni": avanzamento["iscritti"], "in_lista_attesa": avanzamento["in_lista_attesa"],
            "in_attesa_sessione": avanzamento["in_attesa_sessione"]}

@router.get("/{percorso_id}/assegnazioni")
def assegnazioni_percorso(percorso_id: str, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    """Chi ha il percorso e a che punto e' ogni persona, passo per passo."""
    p = db.query(PercorsoFormativo).options(joinedload(PercorsoFormativo.steps)).filter(PercorsoFormativo.id == percorso_id).first()
    if not p: raise HTTPException(404)
    out = []
    for a in db.query(PercorsoAssegnazione).filter(PercorsoAssegnazione.percorso_id == p.id).all():
        persona = db.query(User).filter(User.id == a.user_id).first()
        if not persona:
            continue
        passi = calcola_stato_steps(db, p, a.user_id)
        ufficio = db.query(UserGroup).filter(UserGroup.user_id == a.user_id).first()
        out.append({"user_id": str(a.user_id), "nome": persona.full_name, "attivo": persona.is_active,
                    "ufficio": ufficio.group.name if ufficio and ufficio.group else None, "assegnato_il": a.assegnato_il,
                    "completati": sum(1 for x in passi if x["completato"]), "totale": len(passi), "passi": passi})
    out.sort(key=lambda r: (r["nome"] or "").casefold())
    return out

@router.delete("/{percorso_id}/assegnazioni/{user_id}")
def togli_assegnazione(percorso_id: str, user_id: str, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    """Toglie il percorso dalla persona. Le iscrizioni gia' fatte restano (puo' averne in corso): si annullano dalle sessioni."""
    a = db.query(PercorsoAssegnazione).filter(PercorsoAssegnazione.percorso_id == percorso_id, PercorsoAssegnazione.user_id == user_id).first()
    if not a: raise HTTPException(404)
    p = db.query(PercorsoFormativo).filter(PercorsoFormativo.id == percorso_id).first()
    db.delete(a)
    audit_svc.log_from_request(db, request, user, "UNASSIGN", entity_type="percorso", entity_id=percorso_id, entity_name=p.nome if p else None,
                                detail=f"tolto a {audit_svc.nome_utente(db, user_id)}")
    db.commit()
    return {"ok": True}

def _calcola_stato_steps(db: Session, p: PercorsoFormativo, user_id):
    return calcola_stato_steps(db, p, user_id)

@router.get("/{percorso_id}/stato/{user_id}")
def stato_percorso_utente(percorso_id: str, user_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = db.query(PercorsoFormativo).options(joinedload(PercorsoFormativo.steps)).filter(PercorsoFormativo.id == percorso_id).first()
    if not p: raise HTTPException(404)
    # lo stato formativo di una persona lo vedono lei, la Formazione e chi la guida: non un collega
    if str(user.id) != str(user_id) and not user.ha_poteri_formazione and str(user_id) not in {str(x.id) for x in sottoposti_di(db, user.id)}:
        raise HTTPException(403, "Non puoi vedere lo stato formativo di questa persona")
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
        out.append({"assegnazione_id": str(a.id), "percorso_id": str(p.id), "nome": p.nome, "modalita": p.modalita,
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
    _controlla_steps(data)
    p.nome = data.nome
    p.modalita = data.modalita
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

    _crea_steps(db, p, data)

    db.commit()

    from ..services.percorsi_sync import sincronizza_assegnazioni
    sincronizza_assegnazioni(db, percorso_id=str(p.id))
    db.commit()
    avanza_e_invita(db, percorso_ids=[p.id])          # corsi aggiunti o propedeuticità cambiate: chi ha il percorso si riallinea
    db.refresh(p)
    return _serialize(p)
