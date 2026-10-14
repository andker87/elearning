from fastapi import HTTPException
from sqlalchemy.orm import Session
from ..models.edizione import Edizione
from ..models.iscrizione import Iscrizione, StatoIscrizione

STATI_OCCUPANO_POSTO = (StatoIscrizione.iscritto, StatoIscrizione.completato, StatoIscrizione.non_completato)

def posti_occupati(db: Session, edizione_id: str) -> int:
    return db.query(Iscrizione).filter(Iscrizione.edizione_id == edizione_id,
                                        Iscrizione.stato.in_(STATI_OCCUPANO_POSTO)).count()

def crea_iscrizione_con_capacita(db: Session, edizione: Edizione, user_id: str) -> Iscrizione:
    """Se i posti sono esauriti: lista d'attesa se abilitata (sezione N),
    altrimenti rifiutata. Centralizzato perché iscrizione diretta,
    auto-iscrizione e promozione dalla lista d'attesa devono comportarsi
    allo stesso modo."""
    if edizione.posti_max and posti_occupati(db, edizione.id) >= edizione.posti_max:
        if not edizione.lista_attesa_abilitata:
            raise HTTPException(400, "Posti esauriti per questa sessione")
        stato = StatoIscrizione.in_lista_attesa
    else:
        stato = StatoIscrizione.iscritto
    i = Iscrizione(edizione_id=edizione.id, user_id=user_id, stato=stato)
    db.add(i)
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
