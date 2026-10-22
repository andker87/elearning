from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..models.edizione import Edizione, ModalitaErogazione, StatoEdizione
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.user import User

STATI_OCCUPANO_POSTO = (StatoIscrizione.iscritto, StatoIscrizione.completato, StatoIscrizione.non_completato)

def _aware(d):
    return d if d is None or d.tzinfo is not None else d.replace(tzinfo=timezone.utc)


def fine_prevista(e):
    """Quando finisce la sessione, se si sa. Sempre disponibile: mai. Un video con la sola data di inizio resta disponibile
    «da quell'ora» finche' la Formazione non chiude; le altre modalita' finiscono alla data di fine (o, senza, di inizio)."""
    if e.sempre_aperta:
        return None
    if e.modalita == ModalitaErogazione.video:
        return _aware(e.data_fine)
    return _aware(e.data_fine or e.data_inizio)


def sessione_finita(e) -> bool:
    """Una sessione aperta (pubblicata o in corso) la cui fine e' passata: non accetta piu' iscrizioni."""
    fine = fine_prevista(e)
    return bool(fine is not None and e.stato in (StatoEdizione.pianificata, StatoEdizione.in_corso) and fine < datetime.now(timezone.utc))


def da_chiudere(e) -> bool:
    """Passata la fine prevista e ancora aperta: la Formazione deve chiuderla (il sistema non la chiude da solo)."""
    fine = fine_prevista(e)
    return bool(fine is not None and e.stato in (StatoEdizione.pianificata, StatoEdizione.in_corso) and fine < datetime.now(timezone.utc))


def disponibilita_video(e, adesso=None) -> dict:
    """Quando chi segue puo' guardare il video di una sessione: sempre disponibile = sempre; con data, dall'ora di inizio
    (e fino alla fine, se c'e'). `ok` dice se adesso si puo'; `dal`/`fino` servono a spiegarlo."""
    adesso = adesso or datetime.now(timezone.utc)
    if e.modalita != ModalitaErogazione.video:
        return {"ok": True, "dal": None, "fino": None, "motivo": None}
    if e.stato in (StatoEdizione.chiusa, StatoEdizione.annullata):        # chiusa dalla Formazione (anche prima della fine) o annullata
        return {"ok": False, "dal": _aware(e.data_inizio), "fino": _aware(e.data_fine), "motivo": "scaduto"}
    if e.stato == StatoEdizione.bozza:
        return {"ok": False, "dal": _aware(e.data_inizio), "fino": _aware(e.data_fine), "motivo": "non_ancora"}
    if e.sempre_aperta:
        return {"ok": True, "dal": None, "fino": None, "motivo": None}
    dal, fino = _aware(e.data_inizio), _aware(e.data_fine)
    if dal is not None and adesso < dal:
        return {"ok": False, "dal": dal, "fino": fino, "motivo": "non_ancora"}
    if fino is not None and adesso > fino:
        return {"ok": False, "dal": dal, "fino": fino, "motivo": "scaduto"}
    return {"ok": True, "dal": dal, "fino": fino, "motivo": None}


def autoiscrizione_ammessa(e, corso) -> bool:
    """Ci si puo' iscrivere da soli se il corso lo permette; una sessione «sempre disponibile» e' aperta a tutti per definizione."""
    return bool(corso is not None and (corso.permetti_autoiscrizione or e.sempre_aperta))


def in_catalogo(e, corso) -> bool:
    """La sessione compare nel Catalogo: pubblicata, non finita, corso attivo e iscrizione da soli ammessa."""
    return bool(corso is not None and corso.is_active and e.stato in (StatoEdizione.pianificata, StatoEdizione.in_corso)
                and not sessione_finita(e) and autoiscrizione_ammessa(e, corso))


def posti_occupati(db: Session, edizione_id: str) -> int:
    return db.query(Iscrizione).filter(Iscrizione.edizione_id == edizione_id,
                                        Iscrizione.stato.in_(STATI_OCCUPANO_POSTO)).count()

def posti_occupati_per_sessione(db: Session, edizione_ids) -> dict:
    """{id sessione (testo): posti occupati} per tante sessioni con una sola query."""
    ids = list(edizione_ids)
    if not ids:
        return {}
    righe = (db.query(Iscrizione.edizione_id, func.count(Iscrizione.id))
             .filter(Iscrizione.edizione_id.in_(ids), Iscrizione.stato.in_(STATI_OCCUPANO_POSTO))
             .group_by(Iscrizione.edizione_id).all())
    return {str(eid): n for eid, n in righe}


def crea_iscrizione_con_capacita(db: Session, edizione: Edizione, user_id: str) -> Iscrizione:
    """Se i posti sono esauriti: lista d'attesa se abilitata (sezione N),
    altrimenti rifiutata. Centralizzato perché iscrizione diretta,
    auto-iscrizione e promozione dalla lista d'attesa devono comportarsi
    allo stesso modo."""
    # Un esterno e' un docente di una societa' terza: non e' oggetto di formazione.
    if db.query(User.id).filter(User.id == user_id, User.is_external == True).first():  # noqa: E712
        raise HTTPException(400, "Un utente esterno è un docente: non si iscrive come discente")
    # Blocco della sessione fino al commit: due richieste in parallelo non possono prendere lo stesso ultimo posto.
    db.query(Edizione.id).filter(Edizione.id == edizione.id).with_for_update().first()
    if edizione.posti_max and posti_occupati(db, edizione.id) >= edizione.posti_max:
        if not edizione.lista_attesa_abilitata:
            raise HTTPException(400, "Posti esauriti per questa sessione")
        stato = StatoIscrizione.in_lista_attesa
    else:
        stato = StatoIscrizione.iscritto
    i = Iscrizione(edizione_id=edizione.id, user_id=user_id, stato=stato)
    try:
        with db.begin_nested():  # il vincolo del database ferma anche la doppia iscrizione in parallelo
            db.add(i)
            db.flush()
    except IntegrityError as err:
        raise HTTPException(400, "La persona è già iscritta a questa sessione") from err
    return i

def promuovi_da_lista_attesa(db: Session, edizione_id: str):
    """Dopo un annullamento: se c'è un posto libero, promuove il primo in
    lista d'attesa (FIFO per data di iscrizione). Ritorna l'iscrizione
    promossa (o None) - il chiamante lo usa per mandarle l'invito
    calendario, visto che solo ora ha un posto confermato."""
    ed = db.query(Edizione).filter(Edizione.id == edizione_id).first()
    if ed and ed.posti_max and posti_occupati(db, edizione_id) >= ed.posti_max:
        return None  # nessun posto libero: nessuno da promuovere
    prossimo = (db.query(Iscrizione)
                .filter(Iscrizione.edizione_id == edizione_id, Iscrizione.stato == StatoIscrizione.in_lista_attesa)
                .order_by(Iscrizione.created_at.asc()).first())
    if prossimo:
        prossimo.stato = StatoIscrizione.iscritto
    return prossimo
