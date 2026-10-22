"""Spazi di lavoro: i numeri da mostrare sul selettore (cose da fare in ogni spazio), la lista «Da gestire» della Formazione
e il riepilogo dell'Amministrazione."""
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.autoiscrizione import AutoIscrizioneRichiesta, StatoAutoIscrizione
from ..models.corso import Corso
from ..models.edizione import Edizione, StatoEdizione
from ..models.group import UserGroup
from ..models.job_run import JobRun
from ..models.password_reset import RichiestaResetPassword
from ..models.percorso import PercorsoAssegnazione, PercorsoFormativo
from ..models.richiesta_corso import RichiestaCorso, StatoRichiestaCorso
from ..models.richiesta_iscrizione import RichiestaIscrizione
from ..models.user import User
from ..services.gerarchia import sottoposti_di
from ..services.iscrizioni import da_chiudere, posti_occupati
from ..services.percorsi_iscrizioni import calcola_stato_steps
from .deps import get_current_user, require_admin_tecnico, require_training_admin
from .richieste_iscrizione import _riga as riga_richiesta

router = APIRouter(tags=["spazi"])

_ATTESE_TTL = 60          # secondi: il conto delle attese nei percorsi e' costoso, sul selettore basta fresco di un minuto
_attese_cache = {"t": 0.0, "valore": None}


def _attese_percorsi(db: Session) -> list:
    """Per ogni corso: quante persone dei percorsi aspettano una sessione e quante devono rifarlo."""
    per_corso = {}
    for a, p in (db.query(PercorsoAssegnazione, PercorsoFormativo).join(PercorsoFormativo, PercorsoFormativo.id == PercorsoAssegnazione.percorso_id)
                 .join(User, User.id == PercorsoAssegnazione.user_id).filter(PercorsoFormativo.is_active == True, User.is_active == True).all()):  # noqa: E712
        for s in calcola_stato_steps(db, p, a.user_id):
            if s["stato"] not in ("in_attesa_sessione", "da_rifare"):
                continue
            voce = per_corso.setdefault(s["corso_id"], {"corso_id": s["corso_id"], "corso_titolo": s["corso_titolo"], "in_attesa": 0, "da_rifare": 0, "percorsi": set()})
            voce["in_attesa" if s["stato"] == "in_attesa_sessione" else "da_rifare"] += 1
            voce["percorsi"].add(p.nome)
    out = [{**v, "percorsi": sorted(v["percorsi"])} for v in per_corso.values()]
    return sorted(out, key=lambda v: (-(v["in_attesa"] + v["da_rifare"]), v["corso_titolo"].casefold()))


def _attese_in_cache(db: Session) -> list:
    if _attese_cache["valore"] is None or time.monotonic() - _attese_cache["t"] > _ATTESE_TTL:
        _attese_cache["valore"] = _attese_percorsi(db)
        _attese_cache["t"] = time.monotonic()
    return _attese_cache["valore"]


def _sessioni_da_chiudere(db: Session) -> list:
    out = []
    for e, c in (db.query(Edizione, Corso).join(Corso, Corso.id == Edizione.corso_id)
                 .filter(Edizione.stato.in_((StatoEdizione.pianificata, StatoEdizione.in_corso))).all()):
        if da_chiudere(e):
            out.append({"id": str(e.id), "corso_titolo": c.titolo, "modalita": e.modalita, "data_inizio": e.data_inizio, "data_fine": e.data_fine,
                        "luogo": e.luogo, "n_iscritti": posti_occupati(db, e.id)})
    return sorted(out, key=lambda x: x["data_fine"] or x["data_inizio"] or datetime.min.replace(tzinfo=timezone.utc))


def _n_sessioni_da_chiudere(db: Session) -> int:
    """Quante sessioni sono da chiudere (stessa regola dell'elenco), senza contare gli iscritti: serve ai numeri sul menu."""
    return sum(1 for e in db.query(Edizione).filter(Edizione.stato.in_((StatoEdizione.pianificata, StatoEdizione.in_corso))).all() if da_chiudere(e))


def _richieste_corsi(db: Session) -> list:
    out = []
    for r in db.query(RichiestaCorso).filter(RichiestaCorso.stato == StatoRichiestaCorso.in_attesa).order_by(RichiestaCorso.created_at).all():
        corso = db.query(Corso).filter(Corso.id == r.corso_id).first() if r.corso_id else None
        chi = db.query(User).filter(User.id == r.richiedente_id).first()
        ufficio = db.query(UserGroup).filter(UserGroup.user_id == r.richiedente_id).first()
        out.append({"id": str(r.id), "titolo": corso.titolo if corso else r.argomento, "a_catalogo": corso is not None,
                    "richiedente": chi.full_name if chi else None, "ufficio": ufficio.group.name if ufficio and ufficio.group else None,
                    "persone": len(r.persone), "created_at": r.created_at})
    return out


@router.get("/api/da-gestire")
def da_gestire(db: Session = Depends(get_db), user: User = Depends(require_training_admin)):
    """Tutto quello che aspetta una decisione della Formazione, in un posto solo."""
    richieste = [riga_richiesta(r, db) for r in db.query(RichiestaIscrizione).filter(RichiestaIscrizione.stato == "in_attesa").order_by(RichiestaIscrizione.created_at).all()]
    sessioni = _sessioni_da_chiudere(db)
    corsi = _richieste_corsi(db)
    attese = _attese_percorsi(db)              # qui fresco, non dalla cache: e' la pagina che si sta guardando
    _attese_cache.update({"t": time.monotonic(), "valore": attese})
    return {"richieste_iscrizione": richieste, "sessioni_da_chiudere": sessioni, "richieste_corsi": corsi, "percorsi": attese,
            "totale": len(richieste) + len(sessioni) + len(corsi) + len(attese)}


@router.get("/api/contatori")
def contatori(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """I numeri sul selettore degli spazi e sulle voci del menu: le cose che aspettano te. None = lo spazio non e' tuo."""
    out = {"gestione": None, "amministrazione": None, "team": None}
    if user.ha_poteri_formazione:
        out["gestione"] = (db.query(func.count(RichiestaIscrizione.id)).filter(RichiestaIscrizione.stato == "in_attesa").scalar()
                           + _n_sessioni_da_chiudere(db)
                           + db.query(func.count(RichiestaCorso.id)).filter(RichiestaCorso.stato == StatoRichiestaCorso.in_attesa).scalar()
                           + len(_attese_in_cache(db)))
    if user.is_admin:
        out["amministrazione"] = db.query(func.count(RichiestaResetPassword.id)).filter(RichiestaResetPassword.stato == "in_attesa").scalar()
    sottoposti = [s.id for s in sottoposti_di(db, user.id)]
    if sottoposti:
        out["team"] = db.query(func.count(AutoIscrizioneRichiesta.id)).filter(
            AutoIscrizioneRichiesta.user_id.in_(sottoposti), AutoIscrizioneRichiesta.stato == StatoAutoIscrizione.in_attesa).scalar()
    return out


@router.get("/api/amministrazione/riepilogo")
def riepilogo_amministrazione(db: Session = Depends(get_db), user: User = Depends(require_admin_tecnico)):
    """Persone, accessi e salute della piattaforma in una pagina: il punto di partenza dello spazio Amministrazione."""
    attivi = db.query(User).filter(User.is_active == True).all()  # noqa: E712
    con_ufficio = {r.user_id for r in db.query(UserGroup).all()}
    ultimi = {}
    for job in ("sync_entra", "notifiche_giornaliere", "percorsi_iscrizioni", "rinnovi_automatici"):
        r = db.query(JobRun).filter(JobRun.job_id == job).order_by(JobRun.started_at.desc()).first()
        ultimi[job] = {"started_at": r.started_at, "esito": r.esito, "errore": r.errore} if r else None
    from .admin_tecnico import salute
    s = salute(db, user)
    return {
        "persone": {"attive": len(attivi), "interne": sum(1 for u in attivi if not u.is_external), "esterne": sum(1 for u in attivi if u.is_external),
                    "senza_ufficio": sum(1 for u in attivi if not u.is_external and u.id not in con_ufficio)},
        "richieste_password": db.query(func.count(RichiestaResetPassword.id)).filter(RichiestaResetPassword.stato == "in_attesa").scalar(),
        "lavori": ultimi,
        "accessi": s["accessi"], "smtp": s["smtp"], "storage": s["storage"], "sso": s["sso"], "entra": s["entra"],
    }
