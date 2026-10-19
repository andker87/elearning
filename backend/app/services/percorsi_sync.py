from sqlalchemy.orm import Session
from ..models.percorso import PercorsoFormativo, PercorsoAssegnazione, TriggerAssegnazione
from ..models.group import Group, UserGroup
from ..models.mansione import UserMansione
from ..models.user import User

def _gruppo_e_discendenti(db: Session, group_id: str) -> list[str]:
    """Un gruppo target include anche i suoi sottogruppi (appartenenza
    trasitiva): assegnare un corso al gruppo 'Assicurazioni' deve raggiungere
    anche chi sta solo nel sottogruppo 'Assicurazioni Vita'."""
    ids = [group_id]
    frontiera = [group_id]
    while frontiera:
        figli = db.query(Group.id).filter(Group.parent_id.in_(frontiera)).all()
        nuovi = [str(f[0]) for f in figli if str(f[0]) not in ids]
        ids.extend(nuovi)
        frontiera = nuovi
    return ids

def sincronizza_assegnazioni(db: Session, percorso_id: str = None) -> int:
    """Assegna i Percorsi con trigger automatico (ingresso_azienda / ufficio / mansione) agli
    utenti che li soddisfano e non sono ancora assegnati. Idempotente: può essere
    richiamata a ripetizione (dopo creazione/modifica percorso, dopo modifica utente,
    o manualmente) senza creare doppioni.
    Ritorna il numero di nuove assegnazioni create."""
    q = db.query(PercorsoFormativo).filter(PercorsoFormativo.is_active == True)
    if percorso_id:
        q = q.filter(PercorsoFormativo.id == percorso_id)
    percorsi = q.all()

    creati = 0
    for p in percorsi:
        if p.trigger_tipo == TriggerAssegnazione.ingresso_azienda:
            candidati = db.query(User).filter(User.is_active == True, User.is_external == False,  # noqa: E712
                                              User.data_ingresso.isnot(None)).all()
        elif p.trigger_tipo == TriggerAssegnazione.gruppo and p.trigger_gruppo_id:
            gruppi_ids = _gruppo_e_discendenti(db, str(p.trigger_gruppo_id))
            candidati = db.query(User).join(UserGroup, UserGroup.user_id == User.id).filter(
                UserGroup.group_id.in_(gruppi_ids), User.is_active == True).all()
        elif p.trigger_tipo == TriggerAssegnazione.mansione and p.trigger_mansione_id:
            candidati = db.query(User).join(UserMansione, UserMansione.user_id == User.id).filter(
                UserMansione.mansione_id == p.trigger_mansione_id, User.is_active == True).all()
        else:
            continue  # trigger manuale: nessuna assegnazione automatica

        esistenti = {str(a.user_id) for a in db.query(PercorsoAssegnazione).filter(PercorsoAssegnazione.percorso_id == p.id).all()}
        for u in candidati:
            if str(u.id) in esistenti:
                continue
            db.add(PercorsoAssegnazione(percorso_id=p.id, user_id=u.id))
            creati += 1
    db.flush()
    return creati
