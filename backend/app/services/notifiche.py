from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.edizione import Edizione, StatoEdizione
from ..models.corso import Corso
from ..models.percorso import PercorsoAssegnazione, PercorsoFormativo
from ..models.notification import Notification
from ..models.user import User
from ..config import settings
from .gerarchia import responsabili_di
from .email import invia_email, invia_email_con_allegato, dopo_il_commit, in_sottofondo
from .push import accoda_push
from .calendario import evento_edizione, costruisci_ics

FINESTRA_PREAVVISO_GIORNI = 30

def con_link(db: Session, testo: str, link: str = None) -> str:
    """Aggiunge in fondo all'email il link diretto, se e' impostato l'URL
    pubblico della piattaforma (pagina Piattaforma): senza non si puo' costruire
    un indirizzo valido fuori dal browser, e il testo resta invariato."""
    if not link:
        return testo
    from ..models.azienda import Azienda
    a = db.query(Azienda).first()
    if not a or not a.url_pubblico:
        return testo
    return f"{testo}\n\nApri nella piattaforma: {a.url_pubblico.rstrip('/')}{link}"

def _crea_se_assente(db: Session, user_id, tipo: str, testo: str, dedup_key: str, link: str = None):
    esiste = db.query(Notification).filter(Notification.dedup_key == dedup_key).first()
    if esiste:
        return False
    db.add(Notification(user_id=user_id, tipo=tipo, testo=testo, dedup_key=dedup_key, link=link))
    # Ogni notifica in-app prova anche la via email e la via push (se
    # configurate) - un solo punto di passaggio per tutte le notifiche
    # generate dallo scheduler, scadenze comprese.
    utente = db.query(User).filter(User.id == user_id).first()
    if utente:
        # partono dopo il commit e in sottofondo: centinaia di notifiche non bloccano la richiesta
        dopo_il_commit(db, invia_email, utente.email, "Notifica dalla piattaforma formazione", con_link(db, testo, link))
        accoda_push(db, user_id, "Formazione", testo, link)
    return True

def _escalation_responsabili(db: Session, discente: User, tipo: str, testo: str, dedup_key: str, link: str = None) -> int:
    """Le scadenze di compliance (corso/test) vanno anche al responsabile,
    non solo al discente - è spesso il motivo per cui un audit passa o
    fallisce. Un responsabile derivato dagli uffici (vedi gerarchia.py), mai
    solo un promemoria generico come percorso/edizione imminente."""
    creati = 0
    for responsabile in responsabili_di(db, discente.id):
        if _crea_se_assente(db, responsabile.id, f"{tipo}_responsabile",
                f"{testo} ({discente.full_name})",
                dedup_key=f"{dedup_key}:resp:{responsabile.id}", link=link):
            creati += 1
    return creati

def invia_invito_calendario(db: Session, edizione: Edizione, user_id) -> bool:
    """Invito .ics via mail quando una sessione ha (o si vede fissare) una
    data: niente da fare se la sessione non ha ancora data_inizio, o se
    l'SMTP non è configurato (invia_email_con_allegato fa già quel
    controllo, qui evitiamo solo di costruire l'ics a vuoto)."""
    if not edizione.data_inizio or not settings.smtp_enabled or edizione.stato == StatoEdizione.bozza:
        return False  # una sessione in bozza non e' ancora confermata: l'invito parte quando viene pianificata
    corso = db.query(Corso).filter(Corso.id == edizione.corso_id).first()
    titolo = corso.titolo if corso else "Sessione formativa"
    evento = evento_edizione(edizione, titolo)
    if not evento:
        return False
    utente = db.query(User).filter(User.id == user_id).first()
    if not utente:
        return False
    ics = costruisci_ics([evento])
    corpo = f"In allegato l'invito calendario per \"{titolo}\", il {edizione.data_inizio.strftime('%d/%m/%Y alle %H:%M')}."
    in_sottofondo(invia_email_con_allegato, utente.email, f"Invito: {titolo}", corpo, "invito.ics", ics)
    return True

def invia_comunicazione_edizione(db: Session, destinatari_ids, oggetto: str, messaggio: str, link: str = None) -> int:
    """Annuncio manuale (non deduplicato, a differenza di _crea_se_assente: è
    un'azione esplicita di chi scrive, non un promemoria generato dallo
    scheduler) sugli stessi tre canali - notifica in-app, email, push."""
    inviati = 0
    testo = f"{oggetto} — {messaggio}" if oggetto else messaggio
    for user_id in destinatari_ids:
        utente = db.query(User).filter(User.id == user_id).first()
        if not utente:
            continue
        db.add(Notification(user_id=user_id, tipo="comunicazione_sessione", testo=testo, link=link))
        dopo_il_commit(db, invia_email, utente.email, oggetto, con_link(db, messaggio, link))
        accoda_push(db, user_id, oggetto, messaggio, link)
        inviati += 1
    return inviati

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
        discente = db.query(User).filter(User.id == i.user_id).first()
        if corso and corso.validita_mesi:
            scadenza = i.completato_at + relativedelta(months=corso.validita_mesi)
            if scadenza - now <= timedelta(days=FINESTRA_PREAVVISO_GIORNI):
                stato_txt = "è scaduto" if scadenza <= now else f"scade il {scadenza.strftime('%d/%m/%Y')}"
                testo = f"Il corso \"{corso.titolo}\" {stato_txt}: è previsto un rinnovo."
                dedup_key = f"scadenza_corso:{corso.id}:{i.user_id}:{scadenza.date()}"
                if _crea_se_assente(db, i.user_id, "scadenza_corso", testo, dedup_key=dedup_key):
                    creati += 1
                if discente:
                    creati += _escalation_responsabili(db, discente, "scadenza_corso", testo, dedup_key)
        if i.ripeti_entro and i.ripeti_entro - now <= timedelta(days=FINESTRA_PREAVVISO_GIORNI):
            testo = f"Il corso \"{corso.titolo if corso else ''}\" va ripetuto entro il {i.ripeti_entro.strftime('%d/%m/%Y')} (test non superato)."
            dedup_key = f"ripeti_entro:{i.id}"
            if _crea_se_assente(db, i.user_id, "ripeti_corso", testo, dedup_key=dedup_key):
                creati += 1
            if discente:
                creati += _escalation_responsabili(db, discente, "ripeti_corso", testo, dedup_key)

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
