"""«Il mio team»: cio' che riguarda le persone sotto la responsabilita' di chi guida uno o piu' uffici.

Il team di un responsabile e' fatto dalle persone dei suoi uffici e dei sottouffici (services/gerarchia.sottoposti_di).
Qui non c'e' mai l'elenco di tutte le sessioni della piattaforma: solo quelle in cui sono coinvolte le sue persone,
oppure quelle dei corsi aperti a cui puo' iscriverle o per cui puo' chiedere l'iscrizione."""
from datetime import datetime, timedelta, timezone
from typing import List

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.corso import Corso
from ..models.edizione import Edizione, StatoEdizione
from ..models.group import Group, UserGroup
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.notification import Notification
from ..models.richiesta_iscrizione import RichiestaIscrizione
from ..models.user import User
from ..services import audit as audit_svc
from ..services.durata import durata_effettiva
from ..services.email import dopo_il_commit, invia_email
from ..services.gerarchia import e_responsabile, sottoposti_di, uffici_guidati_da
from ..services.iscrizioni import posti_occupati, sessione_finita
from ..services.percorsi_iscrizioni import corso_bloccato, messaggio_blocco
from .deps import get_current_user
from .auth import _mansioni_per_utente
from .edizioni import _serialize as serializza_edizione

router = APIRouter(prefix="/api/team", tags=["team"])
STATI_APERTI = (StatoEdizione.pianificata, StatoEdizione.in_corso)


def _team(db: Session, user: User) -> list:
    if not e_responsabile(db, user.id):
        raise HTTPException(403, "Non guidi nessun ufficio: questa sezione è per i responsabili")
    return [u for u in sottoposti_di(db, user.id) if u.is_active]


def _persona(u: User, mansioni: dict) -> dict:
    return {"id": str(u.id), "nome": u.nome, "cognome": u.cognome, "full_name": u.full_name, "email": u.email,
            "is_admin": bool(u.is_admin), "is_formazione": bool(u.is_formazione), "is_formatore": bool(u.is_formatore),
            "is_external": bool(u.is_external),
            "mansioni": [{"id": str(m.id), "name": m.name, "color": m.color} for m in mansioni.get(u.id, [])]}


@router.get("/organigramma")
def organigramma(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Gli uffici che guidi, con i sottouffici e le persone di ciascuno (ad albero)."""
    _team(db, user)
    gruppi = db.query(Group).filter(Group.is_ufficio == True).all()  # noqa: E712
    per_id = {g.id: g for g in gruppi}
    figli = {}
    for g in gruppi:
        figli.setdefault(g.parent_id, []).append(g)
    membri = {}
    for r, u in db.query(UserGroup, User).join(User, User.id == UserGroup.user_id).filter(User.is_active == True).all():  # noqa: E712
        membri.setdefault(r.group_id, []).append(u)
    mansioni = _mansioni_per_utente(db)
    guidati = {g.id for g in uffici_guidati_da(db, user.id)}

    def antenato_guidato(g):
        p, visti = per_id.get(g.parent_id), set()
        while p is not None and p.id not in visti:
            if p.id in guidati:
                return True
            visti.add(p.id)
            p = per_id.get(p.parent_id)
        return False

    def nodo(g, visti):
        visti = visti | {g.id}
        persone = sorted(membri.get(g.id, []), key=lambda u: u.chiave_ordine)
        return {"id": str(g.id), "name": g.name, "color": g.color, "e_mio": g.id in guidati,
                "responsabile": {"id": str(g.responsabile_id), "nome": g.responsabile.full_name} if g.responsabile else None,
                "persone": [{**_persona(u, mansioni), "e_responsabile": g.responsabile_id == u.id} for u in persone],
                "figli": [nodo(f, visti) for f in sorted(figli.get(g.id, []), key=lambda x: x.name.casefold()) if f.id not in visti]}

    radici = sorted((per_id[i] for i in guidati if not antenato_guidato(per_id[i])), key=lambda g: g.name.casefold())
    alberi = [nodo(g, set()) for g in radici]

    def conta(n):
        return len(n["persone"]) + sum(conta(f) for f in n["figli"])
    return {"uffici": alberi, "totale_persone": sum(conta(n) for n in alberi)}


@router.get("/persone/{persona_id}/formazione")
def formazione_persona(persona_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Situazione formativa di una persona del tuo team: sessioni (future e passate), corsi completati e scadenze."""
    team = {str(u.id): u for u in _team(db, user)}
    persona = team.get(persona_id)
    if not persona:
        raise HTTPException(403, "Questa persona non è nel tuo team")
    ora = datetime.now(timezone.utc)
    righe = []
    q = (db.query(Iscrizione, Edizione, Corso).join(Edizione, Edizione.id == Iscrizione.edizione_id).join(Corso, Corso.id == Edizione.corso_id)
         .filter(Iscrizione.user_id == persona.id, Iscrizione.stato != StatoIscrizione.annullato))
    for i, e, c in q.all():
        scadenza = (i.completato_at + relativedelta(months=c.validita_mesi)) if i.stato == StatoIscrizione.completato and i.completato_at and c.validita_mesi else None
        righe.append({"edizione_id": str(e.id), "corso_titolo": c.titolo, "stato": i.stato, "edizione_stato": e.stato, "modalita": e.modalita,
                      "data_inizio": e.data_inizio, "luogo": e.luogo, "durata_effettiva_minuti": durata_effettiva(e, c),
                      "completato_at": i.completato_at, "scadenza": scadenza,
                      "scaduto": bool(scadenza and scadenza <= ora), "in_scadenza": bool(scadenza and ora < scadenza <= ora + timedelta(days=60))})
    righe.sort(key=lambda r: (r["data_inizio"] is None, r["data_inizio"] or ora), reverse=False)
    mansioni = _mansioni_per_utente(db, [persona.id])
    in_attesa = (db.query(RichiestaIscrizione, Edizione, Corso).join(Edizione, Edizione.id == RichiestaIscrizione.edizione_id)
                 .join(Corso, Corso.id == Edizione.corso_id)
                 .filter(RichiestaIscrizione.user_id == persona.id, RichiestaIscrizione.stato == "in_attesa").all())
    return {"persona": _persona(persona, mansioni), "iscrizioni": righe,
            "richieste_in_attesa": [{"edizione_id": str(e.id), "corso_titolo": c.titolo, "data_inizio": e.data_inizio} for _, e, c in in_attesa]}


@router.get("/sessioni")
def sessioni_del_team(concluse: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Le sessioni in cui sono iscritte persone del tuo team, con chi di loro partecipa."""
    team = {u.id: u for u in _team(db, user)}
    if not team:
        return []
    q = (db.query(Iscrizione, Edizione).join(Edizione, Edizione.id == Iscrizione.edizione_id)
         .filter(Iscrizione.user_id.in_(list(team)), Iscrizione.stato != StatoIscrizione.annullato))
    if not concluse:
        q = q.filter(Edizione.stato.notin_([StatoEdizione.chiusa, StatoEdizione.annullata]))
    per_edizione = {}
    for i, e in q.all():
        per_edizione.setdefault(e.id, (e, []))[1].append({"user_id": str(i.user_id), "nome": team[i.user_id].full_name, "stato": i.stato})
    out = []
    for e, persone in per_edizione.values():
        out.append({**serializza_edizione(e, db), "persone": sorted(persone, key=lambda p: p["nome"].casefold())})
    ora = datetime.now(timezone.utc)
    out.sort(key=lambda s: (s["data_inizio"] is None, s["data_inizio"] or ora))
    return out


@router.get("/corsi-disponibili")
def corsi_disponibili(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Prossime sessioni dei corsi aperti ai responsabili (iscrizione diretta o su richiesta), con la situazione delle tue persone."""
    team = {u.id: u for u in _team(db, user)}
    ora = datetime.now(timezone.utc)
    sessioni = []
    q = (db.query(Edizione, Corso).join(Corso, Corso.id == Edizione.corso_id)
         .filter(Edizione.stato.in_(STATI_APERTI), Corso.is_active == True,  # noqa: E712
                 Corso.iscrizione_responsabili.in_(["diretta", "su_richiesta"])))
    candidate = []
    for e, c in q.all():
        if sessione_finita(e):
            continue                                          # gia' finita
        candidate.append((e, c))
    ids = [e.id for e, _ in candidate]
    stati = {}
    if ids and team:
        for i in db.query(Iscrizione).filter(Iscrizione.edizione_id.in_(ids), Iscrizione.user_id.in_(list(team)), Iscrizione.stato != StatoIscrizione.annullato).all():
            stati.setdefault(i.edizione_id, {})[str(i.user_id)] = i.stato.value if hasattr(i.stato, "value") else str(i.stato)
        for r in db.query(RichiestaIscrizione).filter(RichiestaIscrizione.edizione_id.in_(ids), RichiestaIscrizione.user_id.in_(list(team)), RichiestaIscrizione.stato == "in_attesa").all():
            stati.setdefault(r.edizione_id, {}).setdefault(str(r.user_id), "richiesta_in_attesa")
    for e, c in candidate:
        s = serializza_edizione(e, db)
        sessioni.append({**s, "modo": c.iscrizione_responsabili,
                         "posti_liberi": (e.posti_max - posti_occupati(db, e.id)) if e.posti_max else None,
                         "persone_stato": stati.get(e.id, {})})
    sessioni.sort(key=lambda s: (s["data_inizio"] is None, s["data_inizio"] or ora))
    uffici = {r.user_id: r.group.name for r in db.query(UserGroup).all() if r.group}
    return {"team": [{"id": str(u.id), "nome": u.full_name, "ufficio": uffici.get(u.id)} for u in sorted(team.values(), key=lambda u: u.chiave_ordine)],
            "sessioni": sessioni}


class RichiestaIn(BaseModel):
    edizione_id: str
    user_ids: List[str]


def _avvisa(db: Session, destinatari, tipo: str, testo: str, link: str, oggetto: str):
    for u in destinatari:
        db.add(Notification(user_id=u.id, tipo=tipo, testo=testo, link=link))
        dopo_il_commit(db, invia_email, u.email, oggetto, testo)       # parte solo a salvataggio riuscito


@router.post("/richieste")
def chiedi_iscrizione(data: RichiestaIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Chiede alla Formazione di iscrivere persone del tuo team a una sessione di un corso «su richiesta»."""
    team = {str(u.id): u for u in _team(db, user)}
    e = db.query(Edizione).filter(Edizione.id == data.edizione_id).first()
    if not e:
        raise HTTPException(404)
    if e.stato not in STATI_APERTI or sessione_finita(e):
        raise HTTPException(400, "Questa sessione non è aperta alle iscrizioni")
    corso = db.query(Corso).filter(Corso.id == e.corso_id).first()
    if not corso or not corso.is_active:
        raise HTTPException(400, "Il corso non è attivo")
    if corso.iscrizione_responsabili != "su_richiesta":
        raise HTTPException(400, "Per questo corso non si chiede l'iscrizione: " + ("puoi iscrivere direttamente le tue persone" if corso.iscrizione_responsabili == "diretta" else "iscrive solo la Formazione"))
    ids = list(dict.fromkeys(data.user_ids))
    if not ids:
        raise HTTPException(400, "Scegli almeno una persona")
    fuori = [i for i in ids if i not in team]
    if fuori:
        raise HTTPException(403, "Puoi chiedere l'iscrizione solo per le persone del tuo team")
    gia_iscritti = {str(i.user_id) for i in db.query(Iscrizione).filter(Iscrizione.edizione_id == e.id, Iscrizione.user_id.in_(ids), Iscrizione.stato != StatoIscrizione.annullato).all()}
    gia_richiesti = {str(r.user_id) for r in db.query(RichiestaIscrizione).filter(RichiestaIscrizione.edizione_id == e.id, RichiestaIscrizione.user_id.in_(ids), RichiestaIscrizione.stato == "in_attesa").all()}
    nuove = [i for i in ids if i not in gia_iscritti and i not in gia_richiesti]
    bloccati = {}
    for i in list(nuove):          # chi ha ancora dei prerequisiti da completare nel suo percorso non si anticipa
        blocco = corso_bloccato(db, i, e.corso_id)
        if blocco:
            bloccati[i] = messaggio_blocco(blocco)
            nuove.remove(i)
    for i in nuove:
        db.add(RichiestaIscrizione(edizione_id=e.id, user_id=i, richiedente_id=user.id))
    if nuove:
        quando = f" del {e.data_inizio.strftime('%d/%m/%Y')}" if e.data_inizio else ""
        nomi = ", ".join(team[i].full_name for i in nuove)
        formazione = db.query(User).filter(User.is_active == True, (User.is_admin == True) | (User.is_formazione == True)).all()  # noqa: E712
        _avvisa(db, formazione, "richiesta_iscrizione",
                f"{user.full_name} chiede di iscrivere {nomi} alla sessione{quando} di «{corso.titolo}».", "/richieste-iscrizione",
                "Nuova richiesta di iscrizione")
        audit_svc.log_from_request(db, request, user, "TEAM_REQUEST", entity_type="edizione", entity_id=str(e.id), entity_name=audit_svc.nome_edizione(db, e),
                                    detail=f"richieste per: {nomi}")
    db.commit()
    return {"richieste": len(nuove), "gia_iscritti": [team[i].full_name for i in ids if i in gia_iscritti],
            "gia_richiesti": [team[i].full_name for i in ids if i in gia_richiesti],
            "bloccati": [{"nome": team[i].full_name, "motivo": m} for i, m in bloccati.items()]}


@router.get("/richieste")
def mie_richieste(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Le richieste di iscrizione fatte da te e il loro esito."""
    _team(db, user)
    righe = (db.query(RichiestaIscrizione, Edizione, Corso, User).join(Edizione, Edizione.id == RichiestaIscrizione.edizione_id)
             .join(Corso, Corso.id == Edizione.corso_id).join(User, User.id == RichiestaIscrizione.user_id)
             .filter(RichiestaIscrizione.richiedente_id == user.id).order_by(RichiestaIscrizione.created_at.desc()).limit(100).all())
    return [{"id": str(r.id), "edizione_id": str(e.id), "corso_titolo": c.titolo, "data_inizio": e.data_inizio, "persona": u.full_name,
             "stato": r.stato, "motivo_rifiuto": r.motivo_rifiuto, "created_at": r.created_at, "valutata_at": r.valutata_at} for r, e, c, u in righe]
