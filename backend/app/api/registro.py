from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from ..database import get_db
from ..models.user import User
from ..models.group import Group, UserGroup
from ..models.corso import Corso
from ..models.edizione import Edizione
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.azienda import Azienda
from ..services.gerarchia import persone_ufficio_e_sottouffici
from ..services.export import esporta
from ..services.etichette import corsi_con_etichette, etichette_del_corso
from .deps import require_training_admin

router = APIRouter(prefix="/api/registro", tags=["registro"])

def _righe(db: Session, ufficio_id: Optional[str], da: Optional[datetime], a: Optional[datetime],
           corso_id: Optional[str] = None, corsi_ammessi: Optional[set] = None):
    """Una riga per ogni (persona, corso) con almeno un'iscrizione non
    annullata - pensato come "stato compliance per persona/reparto in un
    intervallo di tempo" da mostrare a un ispettore, non un log di ogni
    singola edizione. Riusata anche dalla dashboard Ufficio Formazione
    (api/dashboard_formazione.py), da cui il filtro corso_id in più."""
    now = datetime.now(timezone.utc)
    q = (
        db.query(Iscrizione, Edizione, Corso, User)
        .join(Edizione, Iscrizione.edizione_id == Edizione.id)
        .join(Corso, Edizione.corso_id == Corso.id)
        .join(User, Iscrizione.user_id == User.id)
        .filter(Iscrizione.stato != StatoIscrizione.annullato)
    )
    if ufficio_id:
        persone = persone_ufficio_e_sottouffici(db, ufficio_id)
        q = q.filter(Iscrizione.user_id.in_([p.id for p in persone]))
    if corso_id:
        q = q.filter(Corso.id == corso_id)
    if corsi_ammessi is not None:  # filtro per etichette (services/etichette.corsi_con_etichette)
        q = q.filter(Corso.id.in_(corsi_ammessi or [None]))
    if da:
        q = q.filter((Iscrizione.completato_at.is_(None)) | (Iscrizione.completato_at >= da))
    if a:
        q = q.filter((Iscrizione.completato_at.is_(None)) | (Iscrizione.completato_at <= a))

    uffici_per_utente: dict = {}
    etichette_per_corso: dict = {}
    righe = []
    for iscr, ediz, corso, utente in q.order_by(User.full_name, Corso.titolo).all():
        uid = str(utente.id)
        if uid not in uffici_per_utente:
            uffici = (
                db.query(Group.name)
                .join(UserGroup, UserGroup.group_id == Group.id)
                .filter(UserGroup.user_id == utente.id, Group.is_ufficio == True)
                .all()
            )
            uffici_per_utente[uid] = [u[0] for u in uffici]

        scade_il = None
        aggiornamento_disponibile = False
        if iscr.stato == StatoIscrizione.completato:
            versione_obsoleta = iscr.versione_corso is None or iscr.versione_corso < corso.versione_minima_valida
            if versione_obsoleta:
                # Il contenuto è stato aggiornato in modo da richiedere la
                # ripetizione (vedi Corso.versione_minima_valida) - non
                # compliant indipendentemente dalla validità temporale.
                stato_compliance = "da_aggiornare"
            else:
                stato_compliance = "non_applicabile"
                if corso.validita_mesi and iscr.completato_at:
                    scade_il = iscr.completato_at + relativedelta(months=corso.validita_mesi)
                    stato_compliance = "valido" if scade_il > now else "scaduto"
                elif iscr.completato_at:
                    stato_compliance = "valido"
                aggiornamento_disponibile = iscr.versione_corso is not None and iscr.versione_corso < corso.versione
        elif iscr.stato == StatoIscrizione.non_completato:
            stato_compliance = "non_completato"
        else:
            stato_compliance = "in_corso"

        righe.append({
            "iscrizione_id": str(iscr.id), "user_id": uid, "persona": utente.full_name, "email": utente.email,
            "uffici": uffici_per_utente[uid],
            "corso_id": str(corso.id), "corso": corso.titolo,
            "data_edizione": ediz.data_inizio,
            "stato_iscrizione": iscr.stato.value,
            "data_completamento": iscr.completato_at,
            "scade_il": scade_il,
            "stato_compliance": stato_compliance,
            "aggiornamento_disponibile": aggiornamento_disponibile,
            "etichette": etichette_per_corso.setdefault(corso.id, _nomi_etichette(db, corso.id)),
        })
    return righe

def _nomi_etichette(db: Session, corso_id) -> list:
    return [f"{e.famiglia.nome}: {e.nome}" for e in etichette_del_corso(db, corso_id)]

@router.get("")
def registro(ufficio_id: Optional[str] = Query(None), user_id: Optional[str] = Query(None),
             da: Optional[datetime] = Query(None), a: Optional[datetime] = Query(None),
             etichette: Optional[List[str]] = Query(None), db: Session = Depends(get_db),
             user=Depends(require_training_admin)):
    ammessi = corsi_con_etichette(db, etichette)
    return [r for r in _righe(db, ufficio_id, da, a, corsi_ammessi=ammessi) if not user_id or r["user_id"] == user_id]

@router.get("/export")
def registro_export(formato: str = Query("csv"), pagina: str = Query("A4"),
                     ufficio_id: Optional[str] = Query(None), corso_id: Optional[str] = Query(None),
                     user_id: Optional[str] = Query(None), etichette: Optional[List[str]] = Query(None),
                     da: Optional[datetime] = Query(None), a: Optional[datetime] = Query(None),
                     db: Session = Depends(get_db), user=Depends(require_training_admin)):
    righe_dati = [r for r in _righe(db, ufficio_id, da, a, corso_id, corsi_con_etichette(db, etichette)) if not user_id or r["user_id"] == user_id]
    colonne = ["Persona", "Email", "Uffici", "Corso", "Etichette", "Data edizione", "Stato iscrizione",
               "Data completamento", "Scade il", "Stato compliance", "Aggiornamento disponibile"]
    righe = [[
        r["persona"], r["email"], "; ".join(r["uffici"]), r["corso"], "; ".join(r["etichette"]),
        r["data_edizione"], r["stato_iscrizione"], r["data_completamento"], r["scade_il"],
        r["stato_compliance"], r["aggiornamento_disponibile"],
    ] for r in righe_dati]
    azienda = db.query(Azienda).first()
    return esporta(formato, "registro_formazione", "Registro formazione", colonne, righe,
                   pagina, azienda.logo_path if azienda else None)
