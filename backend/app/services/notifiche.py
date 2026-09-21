from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.edizione import Edizione
from ..models.corso import Corso
from ..models.percorso import PercorsoAssegnazione, PercorsoFormativo
from ..models.notification import Notification

FINESTRA_PREAVVISO_GIORNI = 30

def _crea_se_assente(db: Session, user_id, tipo: str, testo: str, dedup_key: str, link: str = None):
    esiste = db.query(Notification).filter(Notification.dedup_key == dedup_key).first()
    if esiste:
        return False
    db.add(Notification(user_id=user_id, tipo=tipo, testo=testo, dedup_key=dedup_key, link=link))
    return True

def genera_notifiche(db: Session) -> int:
    """Genera le notifiche di scadenza/promemoria mancanti. Idempotente tramite
    dedup_key - pensata per essere eseguita periodicamente (scheduler) senza
    creare doppioni. Ritorna il numero di notifiche create."""
    now = datetime.now(timezone.utc)
    creati = 0

    # 1. Scadenze corso (rinnovo periodico) e ripeti_entro (test non superato)
    completate = db.query(Iscrizione).filter(Iscrizione.stato == StatoIscrizione.completato,
                                              Iscrizione.completato_at.isnot(None)).all()
    for i in completate:
        edizione = db.query(Edizione).filter(Edizione.id == i.edizione_id).first()
        corso = db.query(Corso).filter(Corso.id == edizione.corso_id).first() if edizione else None
        if corso and corso.validita_mesi:
            scadenza = i.completato_at + relativedelta(months=corso.validita_mesi)
            if scadenza - now <= timedelta(days=FINESTRA_PREAVVISO_GIORNI):
                stato_txt = "è scaduto" if scadenza <= now else f"scade il {scadenza.strftime('%d/%m/%Y')}"
                if _crea_se_assente(db, i.user_id, "scadenza_corso",
                        f"Il corso \"{corso.titolo}\" {stato_txt}: è previsto un rinnovo.",
                        dedup_key=f"scadenza_corso:{corso.id}:{i.user_id}:{scadenza.date()}"):
                    creati += 1
        if i.ripeti_entro and i.ripeti_entro - now <= timedelta(days=FINESTRA_PREAVVISO_GIORNI):
            if _crea_se_assente(db, i.user_id, "ripeti_corso",
                    f"Il corso \"{corso.titolo if corso else ''}\" va ripetuto entro il {i.ripeti_entro.strftime('%d/%m/%Y')} (test non superato).",
                    dedup_key=f"ripeti_entro:{i.id}"):
                creati += 1

    # 2. Percorsi assegnati non completati (promemoria settimanale)
    settimana = now.strftime("%Y-W%W")
    aperte = db.query(PercorsoAssegnazione).filter(PercorsoAssegnazione.completato == False).all()
    for a in aperte:
        if now - a.assegnato_il < timedelta(days=3):
            continue  # niente promemoria nei primissimi giorni
        p = db.query(PercorsoFormativo).filter(PercorsoFormativo.id == a.percorso_id).first()
        if _crea_se_assente(db, a.user_id, "percorso_promemoria",
                f"Percorso formativo \"{p.nome if p else ''}\" ancora da completare.",
                dedup_key=f"percorso_promemoria:{a.id}:{settimana}"):
            creati += 1

    # 3. Edizioni imminenti (entro 2 giorni) per gli iscritti
    imminenti = db.query(Edizione).filter(
        Edizione.data_inizio.isnot(None),
        Edizione.data_inizio >= now, Edizione.data_inizio <= now + timedelta(days=2),
    ).all()
    for e in imminenti:
        corso = db.query(Corso).filter(Corso.id == e.corso_id).first()
        iscritti = db.query(Iscrizione).filter(Iscrizione.edizione_id == e.id, Iscrizione.stato == StatoIscrizione.iscritto).all()
        for i in iscritti:
            if _crea_se_assente(db, i.user_id, "edizione_imminente",
                    f"Il corso \"{corso.titolo if corso else ''}\" inizia il {e.data_inizio.strftime('%d/%m/%Y alle %H:%M')}.",
                    dedup_key=f"edizione_imminente:{e.id}:{i.user_id}"):
                creati += 1

    db.commit()
    return creati
