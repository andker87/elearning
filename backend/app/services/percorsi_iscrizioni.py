"""Percorsi che iscrivono.

Un percorso assegnato a una persona e' un pacchetto di corsi da svolgere: il sistema la iscrive ai corsi che sono «sbloccati» e,
man mano che ne completa, a quelli che si sbloccano. Per ogni corso sceglie la sessione con la stessa regola del rinnovo
automatico (prima i video sempre disponibili, poi quelli con data gia' iniziata, poi la sessione con data piu' vicina); la
Formazione puo' spostare la persona su un'altra sessione. Se non c'e' nessuna sessione utile il passo resta «in attesa di una
sessione», la Formazione viene avvisata e, appena se ne pubblica una, chi aspettava viene iscritto da solo.

Modalita' del percorso: «libero» (nessun vincolo), «sequenziale» (ogni corso richiede il precedente, nell'ordine) o «con
propedeuticita'» (ogni corso richiede quelli indicati)."""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.corso import Corso
from ..models.edizione import Edizione, ModalitaErogazione, StatoEdizione
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.percorso import PercorsoAssegnazione, PercorsoFormativo
from ..models.user import User
from . import audit as audit_svc
from .iscrizioni import _aware, crea_iscrizione_con_capacita, posti_occupati, sessione_finita
from .notifiche import _crea_se_assente, invia_invito_calendario

log = logging.getLogger(__name__)

STATI_SESSIONE_UTILE = (StatoEdizione.pianificata, StatoEdizione.in_corso)
STATI_ISCRIZIONE_APERTA = (StatoIscrizione.iscritto, StatoIscrizione.in_lista_attesa)


# --- prerequisiti e stato dei passi ------------------------------------------------------------------------------------

def passi_ordinati(p: PercorsoFormativo) -> list:
    return sorted(p.steps, key=lambda s: (s.ordine, str(s.id)))


def prerequisiti(p: PercorsoFormativo) -> Dict[object, list]:
    """Per ogni passo, i passi che deve avere alle spalle, secondo la modalita' del percorso."""
    passi = passi_ordinati(p)
    if p.modalita == "libero":
        return {s.id: [] for s in passi}
    if p.modalita == "sequenziale":
        return {s.id: ([passi[i - 1].id] if i else []) for i, s in enumerate(passi)}
    return {s.id: [pr.richiede_step_id for pr in s.prerequisiti] for s in passi}


def ha_cicli(richiede: Dict[object, list]) -> bool:
    """True se i prerequisiti si richiamano a vicenda (un corso richiederebbe, direttamente o no, se stesso)."""
    stato: Dict[object, int] = {}

    def visita(n) -> bool:
        stato[n] = 1
        for m in richiede.get(n, []):
            if stato.get(m) == 1 or (stato.get(m) is None and visita(m)):
                return True
        stato[n] = 2
        return False

    return any(stato.get(n) is None and visita(n) for n in richiede)


def calcola_stato_steps(db: Session, p: PercorsoFormativo, user_id) -> List[dict]:
    """Lo stato di ogni passo per una persona: completato / iscritto / in lista d'attesa / bloccato / da rifare /
    in attesa di una sessione."""
    passi = passi_ordinati(p)
    if not passi:
        return []
    req = prerequisiti(p)
    corso_ids = [s.corso_id for s in passi]
    corsi = {c.id: c for c in db.query(Corso).filter(Corso.id.in_(corso_ids)).all()}
    righe = (db.query(Iscrizione, Edizione).join(Edizione, Edizione.id == Iscrizione.edizione_id)
             .filter(Iscrizione.user_id == user_id, Edizione.corso_id.in_(corso_ids), Iscrizione.stato != StatoIscrizione.annullato).all())
    per_corso: Dict[object, list] = {}
    for i, e in righe:
        per_corso.setdefault(e.corso_id, []).append((i, e))
    completati = {s.id: any(i.stato == StatoIscrizione.completato for i, _ in per_corso.get(s.corso_id, [])) for s in passi}
    titolo = {s.id: (corsi[s.corso_id].titolo if s.corso_id in corsi else "") for s in passi}
    out = []
    for s in passi:
        sbloccato = all(completati.get(r, False) for r in req[s.id])
        elenco = per_corso.get(s.corso_id, [])
        aperte = [(i, e) for i, e in elenco if i.stato in STATI_ISCRIZIONE_APERTA and e.stato in (StatoEdizione.bozza, *STATI_SESSIONE_UTILE)]
        aperte.sort(key=lambda x: (x[1].data_inizio is None, _aware(x[1].data_inizio) or datetime.min.replace(tzinfo=timezone.utc)))
        if completati[s.id]:
            stato = "completato"
        elif aperte:
            stato = "in_lista_attesa" if aperte[0][0].stato == StatoIscrizione.in_lista_attesa else "iscritto"
        elif not sbloccato:
            stato = "bloccato"
        elif any(i.stato == StatoIscrizione.non_completato for i, _ in elenco):
            stato = "da_rifare"
        else:
            stato = "in_attesa_sessione"
        i, e = aperte[0] if aperte else (None, None)
        out.append({
            "step_id": str(s.id), "corso_id": str(s.corso_id), "corso_titolo": titolo[s.id], "ordine": s.ordine,
            "completato": completati[s.id], "sbloccato": sbloccato, "stato": stato,
            "richiede_titoli": [titolo[r] for r in req[s.id] if not completati.get(r, False) and titolo.get(r)],
            "iscrizione_id": str(i.id) if i else None, "edizione_id": str(e.id) if e else None,
            "data_inizio": e.data_inizio if e else None, "sempre_aperta": bool(e and e.sempre_aperta),
            "modalita_sessione": e.modalita if e else None,
        })
    return out


def corso_bloccato(db: Session, user_id, corso_id) -> Optional[dict]:
    """Il corso e' ancora bloccato per questa persona? Lo e' se in tutti i percorsi che le sono assegnati e lo contengono
    ha dei prerequisiti non completati; in un percorso in cui e' libero (o gia' fatto) o fuori dai percorsi non lo e'."""
    bloccati = []
    for a in db.query(PercorsoAssegnazione).filter(PercorsoAssegnazione.user_id == user_id).all():
        p = db.query(PercorsoFormativo).filter(PercorsoFormativo.id == a.percorso_id, PercorsoFormativo.is_active == True).first()  # noqa: E712
        if not p:
            continue
        passo = next((s for s in p.steps if str(s.corso_id) == str(corso_id)), None)
        if not passo:
            continue
        stato = next(x for x in calcola_stato_steps(db, p, user_id) if x["step_id"] == str(passo.id))
        if stato["completato"] or stato["sbloccato"]:
            return None
        bloccati.append({"percorso": p.nome, "mancano": stato["richiede_titoli"]})
    return bloccati[0] if bloccati else None


def messaggio_blocco(blocco: dict) -> str:
    return f"Prima completa {', '.join('«' + t + '»' for t in blocco['mancano'])} (percorso «{blocco['percorso']}»)"


# --- scelta della sessione ---------------------------------------------------------------------------------------------

def scegli_sessione(db: Session, corso_id, ora: datetime = None, escludi=()) -> Optional[Edizione]:
    """`escludi`: sessioni da non riproporre (quelle a cui la persona e' gia' stata iscritta, anche se poi ha annullato)."""
    ora = ora or datetime.now(timezone.utc)
    candidate = []
    for e in db.query(Edizione).filter(Edizione.corso_id == corso_id, Edizione.stato.in_(STATI_SESSIONE_UTILE)).all():
        if sessione_finita(e) or e.id in escludi:
            continue
        inizio = _aware(e.data_inizio)
        if e.sempre_aperta:
            chiave = (0, ora)
        elif e.modalita == ModalitaErogazione.video:
            chiave = (1, inizio or ora) if (inizio is None or inizio <= ora) else (2, inizio)      # video gia' iniziato: disponibile subito
        elif inizio is None:
            chiave = (3, ora)
        elif inizio >= ora:
            chiave = (2, inizio)
        else:
            continue                                                                              # sessione dal vivo gia' iniziata
        candidate.append((chiave, e))
    candidate.sort(key=lambda x: x[0])
    con_posti = [e for _, e in candidate if e.posti_max is None or posti_occupati(db, e.id) < e.posti_max]
    if con_posti:
        return con_posti[0]
    con_attesa = [e for _, e in candidate if e.lista_attesa_abilitata]
    return con_attesa[0] if con_attesa else None


# --- iscrizione automatica ---------------------------------------------------------------------------------------------

def _data_txt(e: Edizione) -> str:
    return f" del {e.data_inizio.strftime('%d/%m/%Y')}" if e.data_inizio and not e.sempre_aperta else ""


def _avvisa_formazione(db: Session, scoperti: Dict[object, list], da_rifare: Dict[object, list], ora: datetime):
    settimana = ora.strftime("%Y-W%W")
    formazione = db.query(User).filter(User.is_active == True, or_(User.is_admin == True, User.is_formazione == True)).all()  # noqa: E712
    for corso, quanti in scoperti.values():
        for f in formazione:
            _crea_se_assente(db, f.id, "percorso_senza_sessione",
                             f"Percorsi formativi: {quanti} {'persona aspetta' if quanti == 1 else 'persone aspettano'} una sessione di «{corso.titolo}». "
                             "Pubblica una sessione: chi aspetta viene iscritto da solo.",
                             dedup_key=f"percorso_senza_sessione:{corso.id}:{f.id}:{settimana}", link="/sessioni")
    for corso, quanti in da_rifare.values():
        for f in formazione:
            _crea_se_assente(db, f.id, "percorso_da_rifare",
                             f"Percorsi formativi: {quanti} {'persona deve' if quanti == 1 else 'persone devono'} rifare «{corso.titolo}» (non completato): iscrivile a una sessione.",
                             dedup_key=f"percorso_da_rifare:{corso.id}:{f.id}:{settimana}", link="/percorsi")


def avanza_percorsi(db: Session, user_ids=None, corso_ids=None, percorso_ids=None) -> dict:
    """Iscrive ai corsi sbloccati dei percorsi assegnati chi non e' ancora iscritto. Idempotente. Si limita a certe persone,
    a certi corsi (una sessione appena pubblicata) o a certi percorsi. Non fa commit: chi chiama conferma e poi manda gli inviti."""
    ora = datetime.now(timezone.utc)
    corso_ids = {str(c) for c in corso_ids} if corso_ids else None
    q = (db.query(PercorsoAssegnazione, PercorsoFormativo).join(PercorsoFormativo, PercorsoFormativo.id == PercorsoAssegnazione.percorso_id)
         .filter(PercorsoFormativo.is_active == True))  # noqa: E712
    if user_ids:
        q = q.filter(PercorsoAssegnazione.user_id.in_(list(user_ids)))
    if percorso_ids:
        q = q.filter(PercorsoAssegnazione.percorso_id.in_(list(percorso_ids)))
    risultato = {"iscritti": 0, "in_lista_attesa": 0, "in_attesa_sessione": 0, "da_rifare": 0, "inviti": []}
    scoperti: Dict[object, list] = {}
    da_rifare: Dict[object, list] = {}
    utenti: Dict[object, Optional[User]] = {}
    corsi: Dict[object, Optional[Corso]] = {}
    for a, p in q.all():
        if a.user_id not in utenti:
            utenti[a.user_id] = db.query(User).filter(User.id == a.user_id).first()
        u = utenti[a.user_id]
        if not u or not u.is_active or u.is_external:
            continue          # gli esterni (docenti di terzi) non seguono i corsi: non possono essere iscritti ne' restare «in attesa»
        for s in calcola_stato_steps(db, p, a.user_id):
            if corso_ids and s["corso_id"] not in corso_ids:
                continue
            if s["corso_id"] not in corsi:
                corsi[s["corso_id"]] = db.query(Corso).filter(Corso.id == s["corso_id"]).first()
            corso = corsi[s["corso_id"]]
            if not corso or not corso.is_active:
                continue
            if s["stato"] == "da_rifare":
                risultato["da_rifare"] += 1
                da_rifare.setdefault(corso.id, [corso, 0])[1] += 1
                continue
            if s["stato"] != "in_attesa_sessione":
                continue
            avute = {r[0] for r in db.query(Iscrizione.edizione_id).join(Edizione, Edizione.id == Iscrizione.edizione_id)
                     .filter(Iscrizione.user_id == a.user_id, Edizione.corso_id == corso.id).all()}
            e = scegli_sessione(db, corso.id, ora, avute)
            i = None
            if e is not None:
                try:
                    i = crea_iscrizione_con_capacita(db, e, a.user_id)
                    db.flush()
                except HTTPException:
                    i = None              # nel frattempo la sessione si e' riempita: la persona resta in attesa
            if i is None:
                risultato["in_attesa_sessione"] += 1
                scoperti.setdefault(corso.id, [corso, 0])[1] += 1
                continue
            confermata = i.stato == StatoIscrizione.iscritto
            risultato["iscritti" if confermata else "in_lista_attesa"] += 1
            if e.sempre_aperta:
                testo = f"Percorso «{p.nome}»: ora puoi iniziare «{corso.titolo}»."
            elif confermata:
                testo = f"Percorso «{p.nome}»: sei stato iscritto a «{corso.titolo}»{_data_txt(e)}."
            else:
                testo = f"Percorso «{p.nome}»: sei in lista d'attesa per «{corso.titolo}»{_data_txt(e)}."
            _crea_se_assente(db, a.user_id, "percorso_iscrizione", testo, dedup_key=f"percorso_iscrizione:{i.id}", link=f"/sessioni/{e.id}?segui=1")
            esito = "iscritto" if confermata else "in lista d'attesa"
            audit_svc.log_from_request(db, None, None, "PERCORSO_ISCRIZIONE", entity_type="edizione", entity_id=str(e.id),
                                        entity_name=corso.titolo, detail=f"{u.email} - percorso «{p.nome}» - {esito}")
            if confermata and e.data_inizio and not e.sempre_aperta:
                risultato["inviti"].append((e, a.user_id))
    _avvisa_formazione(db, scoperti, da_rifare, ora)
    return risultato


def avanza_e_invita(db: Session, **filtri) -> dict:
    """avanza_percorsi + conferma + inviti del calendario. Da chiamare DOPO il commit dell'operazione principale: se qui
    qualcosa va storto non deve far fallire quella (il giro giornaliero rimedia)."""
    try:
        r = avanza_percorsi(db, **filtri)
        db.commit()
    except Exception as err:                              # noqa: BLE001
        db.rollback()
        log.warning("percorsi: avanzamento non riuscito: %s", err)
        return {"iscritti": 0, "in_lista_attesa": 0, "in_attesa_sessione": 0, "da_rifare": 0}
    for e, uid in r.pop("inviti"):
        try:
            invia_invito_calendario(db, e, uid)
        except Exception as err:                          # noqa: BLE001
            log.warning("percorsi: invito non inviato: %s", err)
    return r


def esegui_percorsi(db: Session) -> str:
    """Giro giornaliero: assegna i percorsi con trigger automatico e iscrive chi aspetta una sessione (rete di sicurezza per
    ogni caso che gli altri punti d'ingresso non hanno visto, per esempio posti liberati o sessioni modificate)."""
    from .percorsi_sync import sincronizza_assegnazioni
    nuove = sincronizza_assegnazioni(db)
    r = avanza_percorsi(db)
    db.commit()
    for e, uid in r.pop("inviti"):
        invia_invito_calendario(db, e, uid)
    return (f"nuove assegnazioni {nuove}, iscritti {r['iscritti']}, in lista d'attesa {r['in_lista_attesa']}, "
            f"in attesa di una sessione {r['in_attesa_sessione']}, da rifare {r['da_rifare']}")
