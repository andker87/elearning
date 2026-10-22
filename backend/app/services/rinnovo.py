"""Rinnovo automatico dei corsi con scadenza (opzione per corso dell'Ufficio Formazione).

A ridosso della scadenza dell'attestato la persona viene iscritta alla prossima
sessione utile del corso. Se non c'e' nessuna sessione disponibile non si fa nulla
in silenzio: l'Ufficio Formazione riceve un avviso con il numero di persone scoperte."""
from datetime import datetime, timedelta, timezone

from dateutil.relativedelta import relativedelta
from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.corso import Corso
from ..models.edizione import Edizione, StatoEdizione
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.user import User
from . import audit as audit_svc
from .iscrizioni import crea_iscrizione_con_capacita, posti_occupati
from .notifiche import _crea_se_assente, _escalation_responsabili, invia_invito_calendario

STATI_SESSIONE_UTILE = (StatoEdizione.pianificata, StatoEdizione.in_corso)
STATI_ISCRIZIONE_APERTA = (StatoIscrizione.iscritto, StatoIscrizione.in_lista_attesa)


def _in_scadenza(db: Session, corso: Corso, ora: datetime) -> list:
    """Persone attive il cui ultimo completamento scade entro i giorni di anticipo
    (o e' gia' scaduto) e che non hanno gia' una iscrizione aperta a una sessione."""
    ultime = {}
    for i in (db.query(Iscrizione).join(Edizione, Edizione.id == Iscrizione.edizione_id)
              .filter(Edizione.corso_id == corso.id, Iscrizione.stato == StatoIscrizione.completato,
                      Iscrizione.completato_at.isnot(None)).all()):
        if i.user_id not in ultime or i.completato_at > ultime[i.user_id].completato_at:
            ultime[i.user_id] = i
    soglia = ora + timedelta(days=corso.rinnovo_giorni_anticipo)
    risultato = []
    for user_id, i in ultime.items():
        scadenza = i.completato_at + relativedelta(months=corso.validita_mesi)
        if i.ripeti_entro and i.ripeti_entro < scadenza:  # test non superato con scadenza breve: vale la data piu' vicina
            scadenza = i.ripeti_entro
        if scadenza > soglia:
            continue
        u = db.query(User).filter(User.id == user_id).first()
        if not u or not u.is_active:
            continue
        # conta solo l'iscrizione a una sessione ancora utilizzabile: una gia' iniziata o in bozza non rinnova nulla
        aperte = (db.query(Edizione).join(Iscrizione, Edizione.id == Iscrizione.edizione_id)
                  .filter(Iscrizione.user_id == user_id, Edizione.corso_id == corso.id,
                          Iscrizione.stato.in_(STATI_ISCRIZIONE_APERTA), Edizione.stato.in_(STATI_SESSIONE_UTILE)).all())
        if not any(e.data_inizio is None or e.data_inizio >= ora for e in aperte):
            risultato.append((u, scadenza))
    return sorted(risultato, key=lambda x: x[1])


def _sessioni_utili(db: Session, corso: Corso, ora: datetime) -> list:
    """Sessioni pianificate non ancora passate, le piu' vicine per prime (quelle senza
    data, tipiche dei videocorsi sempre aperti, in testa)."""
    ed = db.query(Edizione).filter(Edizione.corso_id == corso.id, Edizione.stato.in_(STATI_SESSIONE_UTILE)).all()
    ed = [e for e in ed if e.data_inizio is None or e.data_inizio >= ora]
    return sorted(ed, key=lambda e: (e.data_inizio is not None, e.data_inizio or ora))


def anteprima(db: Session, corso: Corso) -> dict:
    ora = datetime.now(timezone.utc)
    if not corso.validita_mesi:
        return {"persone": [], "sessioni": [], "nota": "Il corso non ha una validità: niente da rinnovare."}
    sessioni = _sessioni_utili(db, corso, ora)
    return {
        "attivo": corso.rinnovo_automatico, "giorni_anticipo": corso.rinnovo_giorni_anticipo,
        "persone": [{"id": str(u.id), "nome": u.full_name, "scadenza": s, "scaduto": s <= ora} for u, s in _in_scadenza(db, corso, ora)],
        "sessioni": [{"id": str(e.id), "data_inizio": e.data_inizio, "modalita": e.modalita,
                      "posti_liberi": (e.posti_max - posti_occupati(db, e.id)) if e.posti_max else None} for e in sessioni],
    }


def _avvisa_formazione(db: Session, corso: Corso, quante: int, ora: datetime):
    settimana = ora.strftime("%Y-W%W")
    for u in db.query(User).filter(User.is_active == True, or_(User.is_admin == True, User.is_formazione == True)).all():  # noqa: E712
        _crea_se_assente(db, u.id, "rinnovo_senza_sessione",
                         f"Rinnovo automatico di \"{corso.titolo}\": {quante} {'persona' if quante == 1 else 'persone'} da rinnovare ma nessuna sessione disponibile. Pianifica una sessione.",
                         dedup_key=f"rinnovo_senza_sessione:{corso.id}:{u.id}:{settimana}", link="/sessioni")


def esegui_rinnovi(db: Session) -> str:
    """Giro giornaliero: iscrive chi sta per scadere nei corsi con rinnovo automatico.
    Idempotente: chi ha gia' una iscrizione aperta al corso non viene toccato."""
    ora = datetime.now(timezone.utc)
    iscritti, in_attesa, scoperti = 0, 0, 0
    for corso in db.query(Corso).filter(Corso.rinnovo_automatico == True, Corso.is_active == True, Corso.validita_mesi.isnot(None)).all():  # noqa: E712
        da_rinnovare = _in_scadenza(db, corso, ora)
        if not da_rinnovare:
            continue
        sessioni = _sessioni_utili(db, corso, ora)
        senza_sessione = 0
        for u, scadenza in da_rinnovare:
            nuova = None
            for e in sessioni:
                try:
                    nuova = crea_iscrizione_con_capacita(db, e, u.id)
                    db.flush()
                    break
                except HTTPException:
                    continue  # sessione piena e senza lista d'attesa: prova la successiva
            if not nuova:
                senza_sessione += 1
                continue
            ed = next(x for x in sessioni if x.id == nuova.edizione_id)
            data_txt = f" il {ed.data_inizio.strftime('%d/%m/%Y')}" if ed.data_inizio else ""
            confermata = nuova.stato == StatoIscrizione.iscritto
            if confermata:
                iscritti += 1
            else:
                in_attesa += 1
            stato_txt = "iscritto/a" if confermata else "messo/a in lista d'attesa"
            testo = f"Il corso \"{corso.titolo}\" {'è scaduto' if scadenza <= ora else 'sta per scadere'}: sei stato {stato_txt} alla sessione{data_txt} per il rinnovo."
            _crea_se_assente(db, u.id, "rinnovo_automatico", testo, dedup_key=f"rinnovo_automatico:{nuova.id}", link="/miei-corsi")
            _escalation_responsabili(db, u, "rinnovo_automatico", testo, f"rinnovo_automatico:{nuova.id}", link="/miei-corsi")
            audit_svc.log_from_request(db, None, None, "RINNOVO_AUTOMATICO", entity_type="edizione", entity_id=str(ed.id),
                                        entity_name=corso.titolo, detail=f"{u.email} - {stato_txt}{data_txt} - scadenza {scadenza.strftime('%d/%m/%Y')}")
            if confermata and ed.data_inizio:
                invia_invito_calendario(db, ed, u.id)
        if senza_sessione:
            scoperti += senza_sessione
            _avvisa_formazione(db, corso, senza_sessione, ora)
    db.commit()
    return f"iscritti {iscritti}, in lista d'attesa {in_attesa}, senza sessione disponibile {scoperti}"
