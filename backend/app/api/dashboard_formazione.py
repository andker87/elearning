from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import Optional, List
from ..database import get_db
from ..models.user import User
from ..models.corso import Corso
from ..models.edizione import Edizione, StatoEdizione
from ..models.percorso import PercorsoFormativo, PercorsoAssegnazione
from ..models.notification import Notification
from ..services.etichette import corsi_con_etichette
from ..services.gerarchia import persone_ufficio_e_sottouffici
from ..services.iscrizioni import posti_occupati
from ..services.email import invia_email
from ..services.push import invia_push
from .registro import _righe
from .percorsi import _calcola_stato_steps
from .deps import require_training_admin

router = APIRouter(prefix="/api/dashboard/formazione", tags=["dashboard-formazione"])

FINESTRA_SCADENZA_GIORNI = 30
FINESTRA_SESSIONI_GIORNI = 14

def _persone_in_scope(db: Session, ufficio_id: Optional[str]) -> List[User]:
    if ufficio_id:
        return persone_ufficio_e_sottouffici(db, ufficio_id)
    return db.query(User).filter(User.is_active == True).all()

def _gap_percorsi(db: Session, persone_ids: set):
    """Persone con un percorso assegnato ma non completato, per ogni step
    sbloccato e non ancora completato: la "scopertura" vera (il corso non è
    mai nemmeno stato iniziato), distinta da scaduto/da aggiornare/non
    completato che riguardano invece chi il corso lo ha già affrontato."""
    assegnazioni = (
        db.query(PercorsoAssegnazione)
        .filter(PercorsoAssegnazione.completato == False, PercorsoAssegnazione.user_id.in_(persone_ids))
        .all()
    )
    per_persona: dict = {}
    percorsi_cache: dict = {}
    for a in assegnazioni:
        pid = str(a.percorso_id)
        if pid not in percorsi_cache:
            percorsi_cache[pid] = (
                db.query(PercorsoFormativo).options(joinedload(PercorsoFormativo.steps))
                .filter(PercorsoFormativo.id == a.percorso_id).first()
            )
        p = percorsi_cache[pid]
        if not p:
            continue
        for s in _calcola_stato_steps(db, p, str(a.user_id)):
            if not s["completato"] and s["sbloccato"]:
                per_persona.setdefault(str(a.user_id), []).append({
                    "corso_id": s["corso_id"], "corso_titolo": s["corso_titolo"],
                    "percorso_nome": p.nome, "tipo": "scoperto",
                })
    return per_persona

@router.get("/kpi")
def kpi(ufficio_id: Optional[str] = Query(None), corso_id: Optional[str] = Query(None), etichette: Optional[List[str]] = Query(None),
        db: Session = Depends(get_db), user=Depends(require_training_admin)):
    now = datetime.now(timezone.utc)
    persone = _persone_in_scope(db, ufficio_id)
    persone_ids = {str(p.id) for p in persone}

    ammessi = corsi_con_etichette(db, etichette)
    righe = _righe(db, ufficio_id, None, None, corso_id, ammessi)
    n_scaduti = sum(1 for r in righe if r["stato_compliance"] == "scaduto")
    n_da_aggiornare = sum(1 for r in righe if r["stato_compliance"] == "da_aggiornare")
    n_non_completato = sum(1 for r in righe if r["stato_compliance"] == "non_completato")
    n_in_scadenza = sum(1 for r in righe if r["stato_compliance"] == "valido" and r["scade_il"]
                        and r["scade_il"] - now <= timedelta(days=FINESTRA_SCADENZA_GIORNI))
    n_aggiornamento_disponibile = sum(1 for r in righe if r["aggiornamento_disponibile"])
    n_valide = sum(1 for r in righe if r["stato_compliance"] in ("valido", "non_applicabile"))

    gap = _gap_percorsi(db, persone_ids) if not corso_id else {}
    if ammessi is not None:
        consentiti = {str(c) for c in ammessi}
        gap = {u: [g for g in v if g["corso_id"] in consentiti] for u, v in gap.items()}
        gap = {u: v for u, v in gap.items() if v}
    n_persone_scoperte = len(gap)
    n_corsi_scoperti = sum(len(v) for v in gap.values())

    now_ed = now
    imminenti = (
        db.query(Edizione)
        .filter(Edizione.data_inizio.isnot(None), Edizione.data_inizio >= now_ed,
                Edizione.data_inizio <= now_ed + timedelta(days=FINESTRA_SESSIONI_GIORNI),
                Edizione.stato != StatoEdizione.chiusa)
        .all()
    )
    n_sessioni_imminenti = len(imminenti)

    totale_righe = len(righe)
    compliance_pct = round(100 * n_valide / totale_righe, 1) if totale_righe else None

    return {
        "n_persone_in_scope": len(persone_ids),
        "compliance_pct": compliance_pct,
        "n_scaduti": n_scaduti,
        "n_da_aggiornare": n_da_aggiornare,
        "n_non_completato": n_non_completato,
        "n_in_scadenza_30gg": n_in_scadenza,
        "n_aggiornamento_disponibile": n_aggiornamento_disponibile,
        "n_persone_scoperte": n_persone_scoperte,
        "n_corsi_scoperti": n_corsi_scoperti,
        "n_sessioni_imminenti": n_sessioni_imminenti,
    }

@router.get("/persone")
def persone_con_problemi(ufficio_id: Optional[str] = Query(None), corso_id: Optional[str] = Query(None),
                          tipo: Optional[str] = Query(None), etichette: Optional[List[str]] = Query(None), db: Session = Depends(get_db),
                          user=Depends(require_training_admin)):
    """Una riga per persona con l'elenco dei problemi aperti (scaduto, da
    aggiornare, non completato, in scadenza entro 30gg, scoperto). `tipo`
    filtra su uno di questi; senza filtro tornano tutte le persone con
    almeno un problema."""
    now = datetime.now(timezone.utc)
    persone = _persone_in_scope(db, ufficio_id)
    persone_ids = {str(p.id) for p in persone}
    persone_by_id = {str(p.id): p for p in persone}

    ammessi = corsi_con_etichette(db, etichette)
    righe = _righe(db, ufficio_id, None, None, corso_id, ammessi)
    problemi_per_persona: dict = {}
    for r in righe:
        if r["user_id"] not in persone_ids:
            continue
        sc = r["stato_compliance"]
        tipo_riga = None
        if sc == "scaduto":
            tipo_riga = "scaduto"
        elif sc == "da_aggiornare":
            tipo_riga = "da_aggiornare"
        elif sc == "non_completato":
            tipo_riga = "non_completato"
        elif sc == "valido" and r["scade_il"] and r["scade_il"] - now <= timedelta(days=FINESTRA_SCADENZA_GIORNI):
            tipo_riga = "in_scadenza"
        if tipo_riga and (tipo is None or tipo == tipo_riga):
            problemi_per_persona.setdefault(r["user_id"], []).append({
                "corso_id": r["corso_id"], "corso_titolo": r["corso"], "tipo": tipo_riga,
                "scade_il": r["scade_il"],
            })

    if tipo is None or tipo == "scoperto":
        if not corso_id:
            consentiti = {str(c) for c in ammessi} if ammessi is not None else None
            for uid, gaps in _gap_percorsi(db, persone_ids).items():
                gaps = [g for g in gaps if consentiti is None or g["corso_id"] in consentiti]
                if gaps:
                    problemi_per_persona.setdefault(uid, []).extend(gaps)

    out = []
    for uid, problemi in problemi_per_persona.items():
        u = persone_by_id.get(uid)
        if not u:
            continue
        out.append({"user_id": uid, "full_name": u.full_name, "email": u.email, "problemi": problemi})
    out.sort(key=lambda x: x["full_name"])
    return out

@router.get("/sessioni-imminenti")
def sessioni_imminenti(giorni: int = Query(FINESTRA_SESSIONI_GIORNI), etichette: Optional[List[str]] = Query(None),
                        db: Session = Depends(get_db), user=Depends(require_training_admin)):
    now = datetime.now(timezone.utc)
    q = (
        db.query(Edizione)
        .filter(Edizione.data_inizio.isnot(None), Edizione.data_inizio >= now,
                Edizione.data_inizio <= now + timedelta(days=giorni), Edizione.stato != StatoEdizione.chiusa)
    )
    ammessi = corsi_con_etichette(db, etichette)
    if ammessi is not None:
        q = q.filter(Edizione.corso_id.in_(ammessi or [None]))
    rows = q.order_by(Edizione.data_inizio).all()
    out = []
    for e in rows:
        corso = db.query(Corso).filter(Corso.id == e.corso_id).first()
        n_iscr = posti_occupati(db, e.id)
        out.append({
            "id": str(e.id), "corso_titolo": corso.titolo if corso else None,
            "data_inizio": e.data_inizio, "modalita": e.modalita,
            "posti_max": e.posti_max, "n_iscritti": n_iscr,
            "posti_liberi": (e.posti_max - n_iscr) if e.posti_max else None,
        })
    return out

class SollecitoIn(BaseModel):
    user_id: str
    corso_id: Optional[str] = None
    messaggio: Optional[str] = None

@router.post("/sollecito")
def sollecito(data: SollecitoIn, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    """Promemoria manuale, su richiesta dell'Ufficio Formazione in qualsiasi
    momento - non passa dal dedup dello scheduler (sezione D/A): un sollecito
    deliberato deve poter essere rimandato anche se ne esiste già uno
    automatico identico."""
    destinatario = db.query(User).filter(User.id == data.user_id).first()
    if not destinatario:
        raise HTTPException(404, "Utente non trovato")
    corso_titolo = None
    if data.corso_id:
        corso = db.query(Corso).filter(Corso.id == data.corso_id).first()
        corso_titolo = corso.titolo if corso else None
    testo = data.messaggio or (
        f"Sollecito dall'Ufficio Formazione: ricordati di occuparti del corso \"{corso_titolo}\"."
        if corso_titolo else "Sollecito dall'Ufficio Formazione: hai delle attività formative da completare."
    )
    db.add(Notification(user_id=destinatario.id, tipo="sollecito_manuale", testo=testo))
    invia_email(destinatario.email, "Sollecito dalla piattaforma formazione", testo)
    invia_push(db, destinatario.id, "Sollecito", testo)
    db.commit()
    return {"ok": True}
