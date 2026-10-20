from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..models.edizione import Edizione, StatoEdizione
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.user import User

STATI_OCCUPANO_POSTO = (StatoIscrizione.iscritto, StatoIscrizione.completato, StatoIscrizione.non_completato)

def sessione_finita(e) -> bool:
    """Una sessione pianificata la cui data (fine, o inizio se manca) e' passata: non accetta piu' iscrizioni."""
    fine = e.data_fine or e.data_inizio
    if fine is None or e.stato != StatoEdizione.pianificata:
        return False
    if fine.tzinfo is None:
        fine = fine.replace(tzinfo=timezone.utc)
    return fine < datetime.now(timezone.utc)


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
