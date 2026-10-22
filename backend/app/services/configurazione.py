"""Esportazione e importazione della configurazione della piattaforma.

Serve a portare le impostazioni da un ambiente all'altro (sviluppo -> produzione), a
ricostruirle dopo un errore o ad avviare una nuova istanza. NON e' un backup: persone,
iscrizioni, esiti e file vivono nel backup dell'infrastruttura. Mai inclusi i segreti
(SMTP, SSO, Graph restano nell'ambiente) ne' le chiavi della piattaforma.

Per ora fuori dal file (da valutare): video, immagini e loghi, template degli attestati,
test e domande, utenti e ruoli di sistema.
L'importazione aggiunge e aggiorna, non cancella mai, e dal confronto mostra sempre
un'anteprima prima di scrivere."""
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.azienda import Azienda
from ..models.corso import AzioneTestNonSuperato, Corso, MODI_ISCRIZIONE_RESPONSABILI
from ..models.etichetta import CorsoEtichetta, Etichetta, EtichettaFamiglia
from ..models.mansione import Mansione
from ..models.group import Group
from ..models.organizzazione import Organizzazione
from ..models.percorso import (MODALITA_PERCORSO, MotivoObbligo, PercorsoFormativo, PercorsoStep, PercorsoStepPrerequisito,
                               TriggerAssegnazione)
from ..models.user import User
from ..version import APP_VERSION
from .percorsi_sync import sincronizza_assegnazioni
from .impronte import impronta

FORMATO = "elearning-configurazione"
SCHEMA = 2   # 2 (2.2.0): mansioni; i gruppi sono solo uffici. I file dello schema 1 si importano ancora (i gruppi non-ufficio diventano mansioni)

CAMPI_AZIENDA = ["ragione_sociale", "partita_iva", "codice_fiscale", "indirizzo", "cap", "citta", "provincia", "nazione", "email", "pec",
                 "nome_piattaforma", "url_pubblico", "privacy_testo"]
CAMPI_ORGANIZZAZIONE = ["tipo", "partita_iva", "accreditamento", "referente", "email", "telefono", "note"]
CAMPI_CORSO = ["descrizione", "validita_mesi", "durata_minuti", "iscrizione_responsabili", "ha_test_finale", "giorni_scadenza_breve", "confronta_pre_post_test",
               "permetti_autoiscrizione", "richiedi_approvazione_responsabile", "richiedi_approvazione_formazione", "rinnovo_automatico", "rinnovo_giorni_anticipo", "is_active"]
ESCLUSI = ["utenti, permessi, uffici e mansioni di ciascuno", "iscrizioni, esiti e attestati", "video, immagini, loghi e icone", "template degli attestati",
           "test e domande", "informativa privacy in PDF", "credenziali e chiavi (SMTP, SSO, Graph, notifiche push)"]


def _chiave(testo: str) -> str:
    return " ".join((testo or "").lower().split())


def _percorso_gruppo(g: Group, per_id: dict) -> str:
    nomi, corrente, visti = [], g, set()
    while corrente is not None and corrente.id not in visti:
        visti.add(corrente.id)
        nomi.append(corrente.name)
        corrente = per_id.get(corrente.parent_id)
    return " / ".join(reversed(nomi))


def esporta(db: Session) -> dict:
    a = db.query(Azienda).first()
    gruppi = db.query(Group).all()
    per_id = {g.id: g for g in gruppi}
    utenti = {u.id: u.email for u in db.query(User).all()}
    corsi = db.query(Corso).order_by(Corso.titolo).all()
    titolo_corso = {c.id: c.titolo for c in corsi}
    famiglie = db.query(EtichettaFamiglia).order_by(EtichettaFamiglia.ordine).all()
    nome_famiglia = {f.id: f.nome for f in famiglie}
    etichette_corso = {}
    for ce, e in db.query(CorsoEtichetta, Etichetta).join(Etichetta, Etichetta.id == CorsoEtichetta.etichetta_id).all():
        etichette_corso.setdefault(ce.corso_id, []).append({"famiglia": nome_famiglia.get(e.famiglia_id), "nome": e.nome})

    nome_mansione = {m.id: m.name for m in db.query(Mansione).all()}
    liberi = sorted(gruppi, key=lambda g: (_percorso_gruppo(g, per_id).count(" / "), _percorso_gruppo(g, per_id).lower()))
    percorsi = []
    for p in db.query(PercorsoFormativo).order_by(PercorsoFormativo.nome).all():
        passi = sorted(p.steps, key=lambda s: s.ordine)
        indice = {s.id: titolo_corso.get(s.corso_id) for s in passi}
        percorsi.append({
            "nome": p.nome, "descrizione": p.descrizione, "motivo": p.motivo.value, "motivo_nota": p.motivo_nota,
            "trigger": p.trigger_tipo.value, "trigger_gruppo": _percorso_gruppo(per_id[p.trigger_gruppo_id], per_id) if p.trigger_gruppo_id in per_id else None,
            "trigger_mansione": nome_mansione.get(p.trigger_mansione_id),
            "attivo": p.is_active, "modalita": p.modalita,
            "passi": [{"corso": titolo_corso.get(s.corso_id), "ordine": s.ordine,
                       "richiede": [indice[r.richiede_step_id] for r in s.prerequisiti if indice.get(r.richiede_step_id)]} for s in passi],
        })
    return {
        "formato": FORMATO, "schema": SCHEMA, "versione_app": APP_VERSION, "esportato_il": datetime.now(timezone.utc).isoformat(),
        "non_incluso": ESCLUSI,
        "azienda": {c: getattr(a, c) for c in CAMPI_AZIENDA} if a else {},
        "gruppi": [{"percorso": _percorso_gruppo(g, per_id), "nome": g.name, "descrizione": g.description, "colore": g.color,
                    "ordine": g.sort_order,
                    "responsabile": utenti.get(g.responsabile_id), "attivo": g.is_active} for g in liberi],
        "mansioni": [{"nome": m.name, "descrizione": m.description, "colore": m.color, "attiva": m.is_active}
                     for m in sorted(db.query(Mansione).all(), key=lambda m: m.name.casefold())],
        "etichette": [{"famiglia": f.nome, "descrizione": f.descrizione, "scelta_multipla": f.scelta_multipla, "obbligatoria": f.obbligatoria,
                       "ordine": f.ordine, "archiviata": f.archiviata,
                       "valori": [{"nome": e.nome, "esclusiva": e.esclusiva, "archiviata": e.archiviata, "ordine": e.ordine} for e in f.etichette]}
                      for f in famiglie],
        "organizzazioni": [{"ragione_sociale": o.ragione_sociale, **{c: getattr(o, c) for c in CAMPI_ORGANIZZAZIONE}}
                           for o in db.query(Organizzazione).order_by(Organizzazione.ragione_sociale).all()],
        "corsi": [{"titolo": c.titolo, **{k: getattr(c, k) for k in CAMPI_CORSO},
                   "azione_test_non_superato": c.azione_test_non_superato.value, "versione": c.versione,
                   "versione_minima_valida": c.versione_minima_valida, "etichette": etichette_corso.get(c.id, [])} for c in corsi],
        "percorsi": percorsi,
    }


class _Rapporto:
    def __init__(self):
        self.sezioni = {n: {"creati": [], "aggiornati": [], "invariati": 0} for n in ("azienda", "etichette", "gruppi", "mansioni", "organizzazioni", "corsi", "percorsi")}
        self.avvisi = []

    def creato(self, sezione, nome): self.sezioni[sezione]["creati"].append(nome)
    def aggiornato(self, sezione, nome, campi): self.sezioni[sezione]["aggiornati"].append({"nome": nome, "campi": campi})
    def invariato(self, sezione): self.sezioni[sezione]["invariati"] += 1
    def dict(self):
        return {"sezioni": self.sezioni, "avvisi": self.avvisi,
                "totali": {"creati": sum(len(s["creati"]) for s in self.sezioni.values()),
                           "aggiornati": sum(len(s["aggiornati"]) for s in self.sezioni.values())}}


def _valida(contenuto):
    if not isinstance(contenuto, dict) or contenuto.get("formato") != FORMATO:
        raise ValueError("Il file non è una configurazione esportata da questa piattaforma.")
    if not isinstance(contenuto.get("schema"), int) or contenuto["schema"] > SCHEMA:
        raise ValueError("Il file è stato creato da una versione più recente della piattaforma: aggiorna prima questa istanza.")


def _imposta(oggetto, valori: dict, campi) -> list:
    """Scrive solo i campi che cambiano e dice quali."""
    cambiati = []
    for campo in campi:
        if campo not in valori:
            continue
        nuovo = valori[campo]
        if getattr(oggetto, campo) != nuovo:
            setattr(oggetto, campo, nuovo)
            cambiati.append(campo)
    return cambiati


def importa(db: Session, contenuto: dict, applica: bool) -> dict:
    """Con applica=False calcola esattamente cosa succederebbe (lavora davvero nel database
    e poi annulla), cosi' l'anteprima non puo' discostarsi dal risultato."""
    _valida(contenuto)
    rapporto = _Rapporto()
    try:
        _azienda(db, contenuto.get("azienda") or {}, rapporto)
        _etichette(db, contenuto.get("etichette") or [], rapporto)
        # File dello schema 1: i gruppi che non erano uffici ora sono mansioni (e i percorsi assegnati a loro seguono).
        gruppi_file = contenuto.get("gruppi") or []
        uffici_file = [d for d in gruppi_file if d.get("ufficio") is not False]
        da_gruppi = [d for d in gruppi_file if d.get("ufficio") is False]
        _gruppi(db, uffici_file, rapporto)
        _mansioni(db, (contenuto.get("mansioni") or []) + [
            {"nome": d["nome"], "descrizione": d.get("descrizione"), "colore": d.get("colore"), "attiva": d.get("attivo")} for d in da_gruppi], rapporto)
        ex_gruppi = {_chiave(d["percorso"]): d["nome"] for d in da_gruppi}
        _organizzazioni(db, contenuto.get("organizzazioni") or [], rapporto)
        _corsi(db, contenuto.get("corsi") or [], rapporto)
        _percorsi(db, contenuto.get("percorsi") or [], rapporto, ex_gruppi)
        if applica:
            sincronizza_assegnazioni(db)
            db.commit()
        else:
            db.rollback()
    except Exception:
        db.rollback()
        raise
    risultato = rapporto.dict()
    risultato["applicato"] = applica
    return risultato


def _azienda(db, dati, rapporto):
    if not dati:
        return
    a = db.query(Azienda).first()
    if not a:
        a = Azienda()
        db.add(a)
        db.flush()
    cambiati = _imposta(a, dati, CAMPI_AZIENDA)
    if cambiati:
        rapporto.aggiornato("azienda", "Dati aziendali e impostazioni", cambiati)
    else:
        rapporto.invariato("azienda")
    db.flush()


def _etichette(db, elenco, rapporto):
    famiglie = {_chiave(f.nome): f for f in db.query(EtichettaFamiglia).all()}
    for d in elenco:
        f = famiglie.get(_chiave(d["famiglia"]))
        valori = {"descrizione": d.get("descrizione"), "scelta_multipla": d.get("scelta_multipla", True),
                  "obbligatoria": d.get("obbligatoria", False), "ordine": d.get("ordine", 0), "archiviata": d.get("archiviata", False)}
        if f is None:
            f = EtichettaFamiglia(nome=d["famiglia"], **valori)
            db.add(f)
            db.flush()
            famiglie[_chiave(f.nome)] = f
            cambiati, nuova = [], True
        else:
            cambiati, nuova = _imposta(f, valori, valori.keys()), False
        presenti = {_chiave(e.nome): e for e in db.query(Etichetta).filter(Etichetta.famiglia_id == f.id).all()}
        aggiunte = []
        for v in d.get("valori", []):
            e = presenti.get(_chiave(v["nome"]))
            dati_v = {"esclusiva": v.get("esclusiva", False), "archiviata": v.get("archiviata", False), "ordine": v.get("ordine", 0)}
            if e is None:
                db.add(Etichetta(famiglia_id=f.id, nome=v["nome"], **dati_v))
                aggiunte.append(v["nome"])
            elif _imposta(e, dati_v, dati_v.keys()):
                cambiati.append(f"etichetta {e.nome}")
        db.flush()
        if nuova:
            rapporto.creato("etichette", f"{f.nome} ({len(aggiunte)} etichette)")
        elif cambiati or aggiunte:
            rapporto.aggiornato("etichette", f.nome, cambiati + [f"aggiunta: {a}" for a in aggiunte])
        else:
            rapporto.invariato("etichette")


def _gruppi(db, elenco, rapporto):
    gruppi = db.query(Group).all()
    per_id = {g.id: g for g in gruppi}
    per_percorso = {_chiave(_percorso_gruppo(g, per_id)): g for g in gruppi}
    for d in sorted(elenco, key=lambda x: x["percorso"].count(" / ")):
        percorso = d["percorso"]
        g = per_percorso.get(_chiave(percorso))
        valori = {}
        for campo, chiave in (("description", "descrizione"), ("color", "colore"),
                              ("sort_order", "ordine"), ("is_active", "attivo")):
            if d.get(chiave) is not None:  # un campo assente nel file non cancella quello esistente
                valori[campo] = d[chiave]
        responsabile = None
        if d.get("responsabile"):
            responsabile = db.query(User).filter(User.email_idx == impronta(d["responsabile"])).first()
            if not responsabile:
                rapporto.avvisi.append(f"Gruppo «{percorso}»: il responsabile {d['responsabile']} non esiste in questa istanza, resta da assegnare.")
        if g is None:
            padre = None
            if " / " in percorso:
                padre = per_percorso.get(_chiave(percorso.rsplit(" / ", 1)[0]))
                if not padre:
                    rapporto.avvisi.append(f"Gruppo «{percorso}» saltato: manca il gruppo sopra di lui.")
                    continue
            g = Group(name=d["nome"], parent_id=padre.id if padre else None, is_ufficio=True,
                      responsabile_id=responsabile.id if responsabile else None,
                      **{"is_active": True, **valori})
            db.add(g)
            db.flush()
            per_percorso[_chiave(percorso)] = g
            per_id[g.id] = g
            rapporto.creato("gruppi", percorso)
            continue
        cambiati = _imposta(g, valori, valori.keys())
        if responsabile and g.responsabile_id != responsabile.id:
            g.responsabile_id = responsabile.id
            cambiati.append("responsabile")
        if cambiati:
            rapporto.aggiornato("gruppi", percorso, cambiati)
        else:
            rapporto.invariato("gruppi")
    db.flush()


def _mansioni(db, elenco, rapporto):
    esistenti = {_chiave(m.name): m for m in db.query(Mansione).all()}
    for d in elenco:
        valori = {}
        for campo, chiave in (("description", "descrizione"), ("color", "colore"), ("is_active", "attiva")):
            if d.get(chiave) is not None:
                valori[campo] = d[chiave]
        m = esistenti.get(_chiave(d["nome"]))
        if m is None:
            m = Mansione(name=d["nome"], **valori)
            db.add(m)
            esistenti[_chiave(m.name)] = m
            rapporto.creato("mansioni", m.name)
            continue
        cambiati = _imposta(m, valori, valori.keys())
        if cambiati:
            rapporto.aggiornato("mansioni", m.name, cambiati)
        else:
            rapporto.invariato("mansioni")
    db.flush()


def _organizzazioni(db, elenco, rapporto):
    esistenti = {_chiave(o.ragione_sociale): o for o in db.query(Organizzazione).all()}
    for d in elenco:
        o = esistenti.get(_chiave(d["ragione_sociale"]))
        if o is None:
            o = Organizzazione(ragione_sociale=d["ragione_sociale"], **{c: d.get(c) for c in CAMPI_ORGANIZZAZIONE})
            db.add(o)
            esistenti[_chiave(o.ragione_sociale)] = o
            rapporto.creato("organizzazioni", o.ragione_sociale)
            continue
        cambiati = _imposta(o, d, CAMPI_ORGANIZZAZIONE)
        if cambiati:
            rapporto.aggiornato("organizzazioni", o.ragione_sociale, cambiati)
        else:
            rapporto.invariato("organizzazioni")
    db.flush()


def _corsi(db, elenco, rapporto):
    esistenti = {_chiave(c.titolo): c for c in db.query(Corso).all()}
    con_test = []
    for d in elenco:
        try:
            azione = AzioneTestNonSuperato(d.get("azione_test_non_superato", "concludi_comunque"))
        except ValueError:
            azione = AzioneTestNonSuperato.concludi_comunque
        valori = {k: d[k] for k in CAMPI_CORSO if k in d}
        valori["azione_test_non_superato"] = azione
        if valori.get("iscrizione_responsabili") not in MODI_ISCRIZIONE_RESPONSABILI:
            valori.pop("iscrizione_responsabili", None)       # valore sconosciuto: si tiene quello del corso (o il predefinito, chiuso)
        if valori.get("rinnovo_automatico") and not valori.get("validita_mesi"):
            valori["rinnovo_automatico"] = False
        c = esistenti.get(_chiave(d["titolo"]))
        nuovo = c is None
        # Le due approvazioni non si sommano, valutando anche quella gia' impostata sul corso che c'e': se il file ne imposta una
        # sola, vince quella e l'altra si spegne; se le imposta entrambe resta quella del responsabile.
        resp = valori.get("richiedi_approvazione_responsabile", False if nuovo else c.richiedi_approvazione_responsabile)
        form = valori.get("richiedi_approvazione_formazione", False if nuovo else c.richiedi_approvazione_formazione)
        if resp and form:
            if "richiedi_approvazione_formazione" in valori and "richiedi_approvazione_responsabile" not in valori:
                valori["richiedi_approvazione_responsabile"] = False
            else:
                valori["richiedi_approvazione_formazione"] = False
        if nuovo:
            c = Corso(titolo=d["titolo"], versione=d.get("versione", 1), versione_minima_valida=d.get("versione_minima_valida", 1), **valori)
            db.add(c)
            esistenti[_chiave(c.titolo)] = c
            cambiati = []
        else:
            cambiati = _imposta(c, valori, valori.keys())  # le versioni di un corso esistente non si toccano
        db.flush()
        cambiati += [f"etichetta {m}" for m in _aggiungi_etichette_corso(db, c, d.get("etichette") or [], rapporto)]  # si aggiungono, non si tolgono
        if nuovo:
            rapporto.creato("corsi", c.titolo)
        elif cambiati:
            rapporto.aggiornato("corsi", c.titolo, cambiati)
        else:
            rapporto.invariato("corsi")
        if d.get("ha_test_finale"):
            con_test.append(d["titolo"])
    if con_test:
        rapporto.avvisi.append(f"{len(con_test)} corsi prevedono un test finale, ma i test non fanno parte del file: vanno ricreati ({', '.join(con_test[:5])}{'…' if len(con_test) > 5 else ''}).")
    db.flush()


def _aggiungi_etichette_corso(db, corso, elenco, rapporto) -> list:
    famiglie = {_chiave(f.nome): f for f in db.query(EtichettaFamiglia).all()}
    attuali = {ce.etichetta_id for ce in db.query(CorsoEtichetta).filter(CorsoEtichetta.corso_id == corso.id).all()}
    aggiunte = []
    for x in elenco:
        f = famiglie.get(_chiave(x.get("famiglia")))
        e = db.query(Etichetta).filter(Etichetta.famiglia_id == f.id).all() if f else []
        e = next((v for v in e if _chiave(v.nome) == _chiave(x.get("nome"))), None)
        if not e:
            rapporto.avvisi.append(f"Corso «{corso.titolo}»: l'etichetta «{x.get('famiglia')}: {x.get('nome')}» non esiste, saltata.")
            continue
        if e.id not in attuali:
            db.add(CorsoEtichetta(corso_id=corso.id, etichetta_id=e.id))
            attuali.add(e.id)
            aggiunte.append(f"{f.nome}: {e.nome}")
    db.flush()
    return aggiunte


def _percorsi(db, elenco, rapporto, ex_gruppi=None):
    mansioni = {_chiave(m.name): m for m in db.query(Mansione).all()}
    ex_gruppi = ex_gruppi or {}
    gruppi = db.query(Group).all()
    per_id = {g.id: g for g in gruppi}
    per_percorso = {_chiave(_percorso_gruppo(g, per_id)): g for g in gruppi}
    corsi = {_chiave(c.titolo): c for c in db.query(Corso).all()}
    esistenti = {_chiave(p.nome): p for p in db.query(PercorsoFormativo).all()}
    for d in elenco:
        try:
            motivo, trigger = MotivoObbligo(d["motivo"]), TriggerAssegnazione(d["trigger"])
        except (KeyError, ValueError):
            rapporto.avvisi.append(f"Percorso «{d.get('nome')}» saltato: motivo o trigger non riconosciuti.")
            continue
        gruppo_trigger = per_percorso.get(_chiave(d["trigger_gruppo"])) if d.get("trigger_gruppo") else None
        mansione_trigger = mansioni.get(_chiave(d["trigger_mansione"])) if d.get("trigger_mansione") else None
        if trigger == TriggerAssegnazione.gruppo and not gruppo_trigger and d.get("trigger_gruppo") and _chiave(d["trigger_gruppo"]) in ex_gruppi:
            trigger = TriggerAssegnazione.mansione      # file vecchio: il gruppo e' diventato una mansione
            mansione_trigger = mansioni.get(_chiave(ex_gruppi[_chiave(d["trigger_gruppo"])]))
        if trigger == TriggerAssegnazione.gruppo and gruppo_trigger and d.get("trigger_gruppo") and _chiave(d["trigger_gruppo"]) in ex_gruppi:
            rapporto.avvisi.append(f"Percorso «{d['nome']}»: il file indicava un gruppo che non era un ufficio («{d['trigger_gruppo']}»), ma qui esiste un ufficio con lo stesso nome ed è quello usato: controlla che sia giusto.")
        if trigger == TriggerAssegnazione.mansione and not mansione_trigger:
            rapporto.avvisi.append(f"Percorso «{d['nome']}»: la mansione non esiste, l'assegnazione automatica non è attiva (trigger manuale).")
            trigger = TriggerAssegnazione.manuale
        if trigger == TriggerAssegnazione.gruppo and not gruppo_trigger:
            rapporto.avvisi.append(f"Percorso «{d['nome']}»: il gruppo «{d.get('trigger_gruppo')}» non esiste, l'assegnazione automatica non è attiva (trigger manuale).")
            trigger = TriggerAssegnazione.manuale
        valori = {"descrizione": d.get("descrizione"), "motivo": motivo, "motivo_nota": d.get("motivo_nota"), "trigger_tipo": trigger,
                  "trigger_gruppo_id": gruppo_trigger.id if gruppo_trigger and trigger == TriggerAssegnazione.gruppo else None,
                  "trigger_mansione_id": mansione_trigger.id if mansione_trigger and trigger == TriggerAssegnazione.mansione else None,
                  "is_active": d.get("attivo", True)}
        if d.get("modalita") in MODALITA_PERCORSO:
            valori["modalita"] = d["modalita"]
        p = esistenti.get(_chiave(d["nome"]))
        nuovo = p is None
        if nuovo and "modalita" not in valori:     # i file di prima non la conoscono: con prerequisiti scritti e' «con propedeuticita'», altrimenti libero
            valori["modalita"] = "propedeuticita" if any(x.get("richiede") for x in d.get("passi", [])) else "libero"
        if nuovo:
            p = PercorsoFormativo(nome=d["nome"], **valori)
            db.add(p)
            db.flush()
            esistenti[_chiave(p.nome)] = p
            cambiati = []
        else:
            cambiati = _imposta(p, valori, valori.keys())
        # passi: si aggiungono quelli che mancano, non se ne tolgono (potrebbero esserci assegnazioni in corso)
        per_corso = {s.corso_id: s for s in p.steps}
        passi_nuovi = []
        for passo in d.get("passi", []):
            corso = corsi.get(_chiave(passo.get("corso")))
            if not corso:
                rapporto.avvisi.append(f"Percorso «{d['nome']}»: il corso «{passo.get('corso')}» non esiste, passo saltato.")
                continue
            if corso.id not in per_corso:
                s = PercorsoStep(percorso_id=p.id, corso_id=corso.id, ordine=passo.get("ordine", len(per_corso)))
                db.add(s)
                db.flush()
                per_corso[corso.id] = s
                passi_nuovi.append(corso.titolo)
        for passo in d.get("passi", []):
            corso = corsi.get(_chiave(passo.get("corso")))
            if not corso or corso.id not in per_corso:
                continue
            for richiesto in passo.get("richiede", []):
                rc = corsi.get(_chiave(richiesto))
                if rc and rc.id in per_corso:
                    esiste = db.query(PercorsoStepPrerequisito).filter(PercorsoStepPrerequisito.step_id == per_corso[corso.id].id,
                                                                       PercorsoStepPrerequisito.richiede_step_id == per_corso[rc.id].id).first()
                    if not esiste:
                        db.add(PercorsoStepPrerequisito(step_id=per_corso[corso.id].id, richiede_step_id=per_corso[rc.id].id))
        db.flush()
        if nuovo:
            rapporto.creato("percorsi", f"{p.nome} ({len(passi_nuovi)} passi)")
        elif cambiati or passi_nuovi:
            rapporto.aggiornato("percorsi", p.nome, cambiati + [f"passo aggiunto: {t}" for t in passi_nuovi])
        else:
            rapporto.invariato("percorsi")
