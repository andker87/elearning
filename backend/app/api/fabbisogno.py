from fastapi import APIRouter, Depends, HTTPException, Request
from ..services import audit as audit_svc
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime, timezone
from ..database import get_db
from ..models.fabbisogno import (
    FabbisognoCampagna, FabbisognoCampagnaInvito, FabbisognoRichiesta,
    StatoCampagna, StatoInvito, StatoFabbisognoRichiesta, PeriodoFabbisogno,
)
from ..models.group import Group
from ..models.notification import Notification
from ..models.user import User
from ..services.export import esporta
from ..services.gerarchia import e_responsabile, uffici_guidati_da, uffici_radice, uffici_figli, ufficio_padre
from .deps import get_current_user, require_training_admin

router = APIRouter(prefix="/api/fabbisogno", tags=["fabbisogno"])

# --- Campagne (HR) ---

class CampagnaIn(BaseModel):
    titolo: str
    descrizione: Optional[str] = None
    scadenza: Optional[datetime] = None

def _serialize_campagna(c: FabbisognoCampagna, db: Session = None):
    dati = {"id": str(c.id), "titolo": c.titolo, "descrizione": c.descrizione,
            "scadenza": c.scadenza, "stato": c.stato, "created_at": c.created_at}
    if db is not None:
        per_stato = dict(db.query(FabbisognoCampagnaInvito.stato, func.count(FabbisognoCampagnaInvito.id))
                         .filter(FabbisognoCampagnaInvito.campagna_id == c.id).group_by(FabbisognoCampagnaInvito.stato).all())
        dati.update({
            "inviti_da_decidere": per_stato.get(StatoInvito.da_decidere, 0),
            "inviti_delegati": per_stato.get(StatoInvito.delegato, 0),
            "inviti_risposti": per_stato.get(StatoInvito.risposto, 0),
            "richieste": db.query(func.count(FabbisognoRichiesta.id)).filter(FabbisognoRichiesta.campagna_id == c.id).scalar() or 0,
        })
    return dati

@router.post("/campagne")
def crea_campagna(data: CampagnaIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_training_admin)):
    c = FabbisognoCampagna(titolo=data.titolo, descrizione=data.descrizione,
                            scadenza=data.scadenza, creata_da_id=user.id)
    db.add(c); db.flush()
    for radice in uffici_radice(db):
        db.add(FabbisognoCampagnaInvito(campagna_id=c.id, ufficio_id=radice.id))
    audit_svc.log_from_request(db, request, user, "CREATE", entity_type="campagna_fabbisogno", entity_id=str(c.id), entity_name=c.titolo)
    db.commit(); db.refresh(c)
    return _serialize_campagna(c)

@router.get("/campagne")
def list_campagne(db: Session = Depends(get_db), user: User = Depends(require_training_admin)):
    rows = db.query(FabbisognoCampagna).order_by(FabbisognoCampagna.created_at.desc()).all()
    return [_serialize_campagna(c, db) for c in rows]

@router.put("/campagne/{campagna_id}/chiudi")
def chiudi_campagna(campagna_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(require_training_admin)):
    c = db.query(FabbisognoCampagna).filter(FabbisognoCampagna.id == campagna_id).first()
    if not c: raise HTTPException(404)
    c.stato = StatoCampagna.chiusa
    audit_svc.log_from_request(db, request, user, "CLOSE", entity_type="campagna_fabbisogno", entity_id=str(c.id), entity_name=c.titolo)
    db.commit()
    return _serialize_campagna(c)

# --- Inviti (responsabili, flusso A) ---

MAX_RIGHE = 50

class RispostaIn(BaseModel):
    argomento: str
    note: Optional[str] = None
    periodo: Optional[PeriodoFabbisogno] = None
    riferimento_periodo: Optional[str] = None
    numero_persone_stimate: Optional[int] = None

class RisposteIn(BaseModel):
    """Una risposta puo' contenere piu' esigenze (una per riga)."""
    righe: List[RispostaIn]

def _righe_valide(righe: List[RispostaIn]) -> List[RispostaIn]:
    pulite = []
    for r in righe:
        r.argomento = (r.argomento or "").strip()
        if r.argomento:
            pulite.append(r)
    if not pulite:
        raise HTTPException(400, "Indica almeno un argomento")
    if len(pulite) > MAX_RIGHE:
        raise HTTPException(400, f"Troppe righe in un solo invio (massimo {MAX_RIGHE})")
    return pulite

def _serialize_invito(i: FabbisognoCampagnaInvito, db: Session):
    ufficio = db.query(Group).filter(Group.id == i.ufficio_id).first()
    figli = uffici_figli(db, i.ufficio_id)
    risposte = db.query(FabbisognoRichiesta).filter(FabbisognoRichiesta.campagna_id == i.campagna_id,
                                                      FabbisognoRichiesta.ufficio_origine_id == i.ufficio_id).count()
    return {"id": str(i.id), "ufficio_id": str(i.ufficio_id), "ufficio_nome": ufficio.name if ufficio else None,
            "stato": i.stato, "sotto_uffici": [f.name for f in figli], "risposte": risposte, "created_at": i.created_at}

def _invita_uffici_radice_mancanti(db: Session):
    """Una campagna aperta raggiunge anche gli uffici di primo livello creati dopo
    il suo avvio: senza questo, chi crea l'ufficio (o ne cambia il responsabile)
    a campagna gia' partita non riceverebbe mai l'invito."""
    aperte = db.query(FabbisognoCampagna).filter(FabbisognoCampagna.stato == StatoCampagna.aperta).all()
    if not aperte:
        return
    radici = uffici_radice(db)
    invitati = {(i.campagna_id, i.ufficio_id) for i in db.query(FabbisognoCampagnaInvito).all()}
    creati = False
    for c in aperte:
        for r in radici:
            if (c.id, r.id) not in invitati:
                db.add(FabbisognoCampagnaInvito(campagna_id=c.id, ufficio_id=r.id))
                creati = True
    if creati:
        db.commit()

@router.get("/inviti/miei")
def miei_inviti(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Campagne aperte che riguardano gli uffici che guidi, raggruppate per campagna:
    chi guida piu' uffici vede ogni campagna una volta sola, con una riga per ufficio
    (anche quelli gia' gestiti, cosi' si vede cosa e' stato fatto)."""
    uffici_ids = [u.id for u in uffici_guidati_da(db, user.id)]
    if not uffici_ids:
        return []
    _invita_uffici_radice_mancanti(db)
    rows = (db.query(FabbisognoCampagnaInvito, FabbisognoCampagna)
            .join(FabbisognoCampagna, FabbisognoCampagna.id == FabbisognoCampagnaInvito.campagna_id)
            .filter(FabbisognoCampagnaInvito.ufficio_id.in_(uffici_ids), FabbisognoCampagna.stato == StatoCampagna.aperta)
            .order_by(FabbisognoCampagna.created_at.desc()).all())
    campagne = {}
    for invito, c in rows:
        voce = campagne.setdefault(str(c.id), {"campagna_id": str(c.id), "titolo": c.titolo, "descrizione": c.descrizione,
                                               "scadenza": c.scadenza, "inviti": []})
        voce["inviti"].append(_serialize_invito(invito, db))
    return list(campagne.values())

def _verifica_invito_di(db: Session, invito_id: str, user_id: str) -> FabbisognoCampagnaInvito:
    invito = db.query(FabbisognoCampagnaInvito).filter(FabbisognoCampagnaInvito.id == invito_id).with_for_update().first()
    if not invito: raise HTTPException(404)
    campagna = db.query(FabbisognoCampagna).filter(FabbisognoCampagna.id == invito.campagna_id).first()
    if campagna and campagna.stato == StatoCampagna.chiusa:
        raise HTTPException(400, "La campagna è chiusa")
    ufficio = db.query(Group).filter(Group.id == invito.ufficio_id).first()
    if not ufficio or str(ufficio.responsabile_id) != str(user_id):
        raise HTTPException(403, "Non sei il responsabile di questo ufficio")
    if invito.stato != StatoInvito.da_decidere:
        raise HTTPException(400, "Invito già gestito")
    return invito

@router.post("/inviti/{invito_id}/delega")
def delega_invito(invito_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    invito = _verifica_invito_di(db, invito_id, user.id)
    figli = uffici_figli(db, invito.ufficio_id)
    if not figli:
        raise HTTPException(400, "Il tuo ufficio non ha sotto-uffici: puoi solo rispondere direttamente")
    invito.stato = StatoInvito.delegato
    for figlio in figli:
        db.add(FabbisognoCampagnaInvito(campagna_id=invito.campagna_id, ufficio_id=figlio.id))
    db.commit()
    return {"ok": True, "delegato_a": [str(f.id) for f in figli]}

def _crea_richieste(db: Session, righe: List[RispostaIn], ufficio: Group, user: User, campagna_id=None):
    padre = ufficio_padre(db, ufficio)
    create = []
    for riga in righe:
        r = FabbisognoRichiesta(
            campagna_id=campagna_id, ufficio_origine_id=ufficio.id,
            ufficio_in_revisione_presso_id=padre.id if padre else None,
            creata_da_id=user.id, argomento=riga.argomento, note=(riga.note or "").strip() or None,
            periodo=riga.periodo, riferimento_periodo=(riga.riferimento_periodo or "").strip() or None,
            numero_persone_stimate=riga.numero_persone_stimate,
            stato=StatoFabbisognoRichiesta.in_revisione if padre else StatoFabbisognoRichiesta.approvata_hr,
        )
        db.add(r)
        create.append(r)
    return create

@router.post("/inviti/{invito_id}/rispondi")
def rispondi_invito(invito_id: str, data: RisposteIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    invito = _verifica_invito_di(db, invito_id, user.id)
    righe = _righe_valide(data.righe)
    ufficio = db.query(Group).filter(Group.id == invito.ufficio_id).first()
    create = _crea_richieste(db, righe, ufficio, user, invito.campagna_id)
    invito.stato = StatoInvito.risposto
    db.commit()
    ctx = _Contesto(db)  # una sola volta, non una per riga
    return [_serialize_richiesta(r, db, ctx) for r in create]

# --- Richieste spontanee (flusso B) ---

class RichiestaSpontaneaIn(RisposteIn):
    ufficio_id: str

@router.post("/richieste")
def crea_richiesta_spontanea(data: RichiestaSpontaneaIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not e_responsabile(db, user.id):
        raise HTTPException(403, "Solo un responsabile può aprire una richiesta di fabbisogno")
    ufficio = db.query(Group).filter(Group.id == data.ufficio_id, Group.is_ufficio == True).first()
    if not ufficio or str(ufficio.responsabile_id) != str(user.id):
        raise HTTPException(403, "Non sei il responsabile dell'ufficio indicato")
    create = _crea_richieste(db, _righe_valide(data.righe), ufficio, user)
    db.commit()
    ctx = _Contesto(db)  # una sola volta, non una per riga
    return [_serialize_richiesta(r, db, ctx) for r in create]

# --- Revisione a cascata (responsabili) e coda finale (HR) ---

class _Contesto:
    """Tutto cio' che serve a descrivere le richieste (nomi, campagne, fusioni), caricato
    una volta sola: le liste con centinaia di righe non fanno una query per campo."""
    def __init__(self, db: Session):
        self.gruppi = {g.id: g.name for g in db.query(Group).all()}
        self.utenti = {u.id: u.full_name for u in db.query(User).all()}
        self.campagne = {c.id: c.titolo for c in db.query(FabbisognoCampagna).all()}
        self.righe = {r.id: r for r in db.query(FabbisognoRichiesta).all()}
        self.figli = {}
        for r in self.righe.values():
            if r.fusa_in_id:
                self.figli.setdefault(r.fusa_in_id, []).append(r)

    def foglie(self, r):
        """Le richieste originali dietro a una richiesta (lei stessa se non e' una fusione)."""
        figli = self.figli.get(r.id)
        if not figli:
            return [r]
        return [f for c in figli for f in self.foglie(c)]

    def radice(self, r):
        while r.fusa_in_id and r.fusa_in_id in self.righe:
            r = self.righe[r.fusa_in_id]
        return r


def _serialize_richiesta(r: FabbisognoRichiesta, db: Session, ctx: "_Contesto" = None):
    ctx = ctx or _Contesto(db)
    foglie = ctx.foglie(r)
    radice = ctx.radice(r)
    unita_in = ctx.righe.get(r.fusa_in_id) if r.fusa_in_id else None
    return {
        "campagna_titolo": ctx.campagne.get(r.campagna_id),
        "id": str(r.id), "campagna_id": str(r.campagna_id) if r.campagna_id else None,
        "ufficio_origine_id": str(r.ufficio_origine_id), "ufficio_origine_nome": ctx.gruppi.get(r.ufficio_origine_id),
        "ufficio_in_revisione_presso_nome": ctx.gruppi.get(r.ufficio_in_revisione_presso_id),
        "creata_da_nome": ctx.utenti.get(r.creata_da_id),
        "argomento": r.argomento, "note": r.note, "periodo": r.periodo,
        "riferimento_periodo": r.riferimento_periodo, "numero_persone_stimate": r.numero_persone_stimate,
        "stato": r.stato, "motivo_rifiuto": r.motivo_rifiuto, "created_at": r.created_at,
        # fusioni e provenienza
        "e_unione": bool(ctx.figli.get(r.id)), "n_origini": len(foglie),
        "uffici_origine": sorted({ctx.gruppi.get(f.ufficio_origine_id) or "?" for f in foglie}),
        "uffici_origine_ids": sorted({str(f.ufficio_origine_id) for f in foglie}),
        "unita_in": {"id": str(unita_in.id), "argomento": unita_in.argomento, "ufficio_nome": ctx.gruppi.get(unita_in.ufficio_origine_id),
                     "creata_da_nome": ctx.utenti.get(unita_in.creata_da_id), "data": unita_in.created_at} if unita_in else None,
        # dove si trova davvero, seguendo le fusioni fino alla richiesta che sta salendo
        "stato_effettivo": radice.stato, "presso_effettivo_nome": ctx.gruppi.get(radice.ufficio_in_revisione_presso_id),
        "motivo_rifiuto_effettivo": radice.motivo_rifiuto,
    }

@router.get("/richieste/da-revisionare")
def richieste_da_revisionare(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    uffici_ids = [u.id for u in uffici_guidati_da(db, user.id)]
    if not uffici_ids:
        return []
    rows = (db.query(FabbisognoRichiesta)
            .filter(FabbisognoRichiesta.ufficio_in_revisione_presso_id.in_(uffici_ids),
                    FabbisognoRichiesta.stato == StatoFabbisognoRichiesta.in_revisione)
            .all())
    ctx = _Contesto(db)
    return sorted([_serialize_richiesta(r, db, ctx) for r in rows],
                  key=lambda x: (_normalizza(x["argomento"]), (x["ufficio_origine_nome"] or "").lower()))

@router.get("/richieste/mie")
def mie_richieste(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (db.query(FabbisognoRichiesta).filter(FabbisognoRichiesta.creata_da_id == user.id)
            .order_by(FabbisognoRichiesta.created_at.desc()).all())
    ctx = _Contesto(db)
    return [_serialize_richiesta(r, db, ctx) for r in rows]

class ApprovaIn(BaseModel):
    argomento: Optional[str] = None
    note: Optional[str] = None
    periodo: Optional[PeriodoFabbisogno] = None
    riferimento_periodo: Optional[str] = None
    numero_persone_stimate: Optional[int] = None

def _verifica_revisore(db: Session, richiesta_id: str, user_id: str) -> FabbisognoRichiesta:
    if not _e_uuid(str(richiesta_id)):
        raise HTTPException(404, "Richiesta non trovata")
    r = db.query(FabbisognoRichiesta).filter(FabbisognoRichiesta.id == richiesta_id).first()
    if not r: raise HTTPException(404)
    if r.stato != StatoFabbisognoRichiesta.in_revisione or not r.ufficio_in_revisione_presso_id:
        raise HTTPException(400, "Richiesta non in attesa di revisione")
    ufficio = db.query(Group).filter(Group.id == r.ufficio_in_revisione_presso_id).first()
    if not ufficio or str(ufficio.responsabile_id) != str(user_id):
        raise HTTPException(403, "Non sei il responsabile di questo ufficio")
    return r

def _sposta_su(db: Session, r: FabbisognoRichiesta):
    ufficio_corrente = db.query(Group).filter(Group.id == r.ufficio_in_revisione_presso_id).first()
    padre = ufficio_padre(db, ufficio_corrente)
    r.ufficio_in_revisione_presso_id = padre.id if padre else None
    r.stato = StatoFabbisognoRichiesta.in_revisione if padre else StatoFabbisognoRichiesta.approvata_hr

@router.put("/richieste/{richiesta_id}/approva")
def approva_richiesta(richiesta_id: str, request: Request, data: ApprovaIn = ApprovaIn(),
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = _verifica_revisore(db, richiesta_id, user.id)
    for campo in ("argomento", "note", "periodo", "riferimento_periodo", "numero_persone_stimate"):
        val = getattr(data, campo)
        if val is not None: setattr(r, campo, val)
    _sposta_su(db, r)
    audit_svc.log_from_request(db, request, user, "APPROVE", entity_type="richiesta_fabbisogno", entity_id=str(r.id), entity_name=r.argomento)
    db.commit()
    return _serialize_richiesta(r, db)

class RifiutaIn(BaseModel):
    motivo: Optional[str] = None

@router.put("/richieste/{richiesta_id}/rifiuta")
def rifiuta_richiesta(richiesta_id: str, data: RifiutaIn, request: Request,
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = _verifica_revisore(db, richiesta_id, user.id)
    r.stato = StatoFabbisognoRichiesta.rifiutata
    r.motivo_rifiuto = (data.motivo or "").strip() or None
    audit_svc.log_from_request(db, request, user, "REJECT", entity_type="richiesta_fabbisogno", entity_id=str(r.id), entity_name=r.argomento, detail=r.motivo_rifiuto)
    db.commit()
    return _serialize_richiesta(r, db)

class MultipleIn(BaseModel):
    ids: List[str]
    motivo: Optional[str] = None

@router.put("/richieste/approva-multiple")
def approva_multiple(data: MultipleIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Tutto o niente: se una sola richiesta non e' tua da valutare non cambia nulla."""
    if not data.ids:
        raise HTTPException(400, "Nessuna richiesta selezionata")
    rows = [_verifica_revisore(db, i, user.id) for i in dict.fromkeys(data.ids)]
    for r in rows:
        _sposta_su(db, r)
        audit_svc.log_from_request(db, request, user, "APPROVE", entity_type="richiesta_fabbisogno", entity_id=str(r.id), entity_name=r.argomento)
    db.commit()
    return {"approvate": len(rows)}

@router.put("/richieste/rifiuta-multiple")
def rifiuta_multiple(data: MultipleIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not data.ids:
        raise HTTPException(400, "Nessuna richiesta selezionata")
    rows = [_verifica_revisore(db, i, user.id) for i in dict.fromkeys(data.ids)]
    motivo = (data.motivo or "").strip() or None
    for r in rows:
        r.stato = StatoFabbisognoRichiesta.rifiutata
        r.motivo_rifiuto = motivo
        audit_svc.log_from_request(db, request, user, "REJECT", entity_type="richiesta_fabbisogno", entity_id=str(r.id), entity_name=r.argomento, detail=motivo)
    db.commit()
    return {"rifiutate": len(rows)}

# --- Fusione di richieste simili --------------------------------------------------------
# Chi sta valutando richieste dei sotto-uffici puo' unire quelle sullo stesso tema in una
# sola, che prosegue la salita al posto delle originali. Le originali non si toccano:
# restano con stato "fusa" e un puntatore alla richiesta che le contiene, quindi a ogni
# livello (e per chi le ha scritte) la provenienza e' sempre ricostruibile.

class UnisciIn(BaseModel):
    ids: List[str]
    argomento: str
    note: Optional[str] = None
    periodo: Optional[PeriodoFabbisogno] = None
    riferimento_periodo: Optional[str] = None
    numero_persone_stimate: Optional[int] = None

@router.post("/richieste/unisci")
def unisci_richieste(data: UnisciIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ids = list(dict.fromkeys(data.ids))
    if len(ids) < 2:
        raise HTTPException(400, "Servono almeno due richieste da unire")
    argomento = (data.argomento or "").strip()
    if not argomento:
        raise HTTPException(400, "Indica l'argomento della richiesta unita")
    rows = [_verifica_revisore(db, i, user.id) for i in ids]
    if len({r.ufficio_in_revisione_presso_id for r in rows}) != 1:
        raise HTTPException(400, "Le richieste devono essere in attesa presso lo stesso ufficio")
    if len({r.campagna_id for r in rows}) != 1:
        raise HTTPException(400, "Non si uniscono richieste di campagne diverse, né una campagna con una richiesta spontanea")
    ufficio = db.query(Group).filter(Group.id == rows[0].ufficio_in_revisione_presso_id).first()
    padre = ufficio_padre(db, ufficio)
    comuni = lambda campo: {getattr(r, campo) for r in rows}
    periodo = data.periodo if data.periodo is not None else (next(iter(comuni("periodo"))) if len(comuni("periodo")) == 1 else None)
    riferimento = (data.riferimento_periodo or "").strip() or (next(iter(comuni("riferimento_periodo"))) if len(comuni("riferimento_periodo")) == 1 else None)
    persone = data.numero_persone_stimate if data.numero_persone_stimate is not None else sum(r.numero_persone_stimate or 0 for r in rows)
    unione = FabbisognoRichiesta(
        campagna_id=rows[0].campagna_id, ufficio_origine_id=ufficio.id,
        ufficio_in_revisione_presso_id=padre.id if padre else None, creata_da_id=user.id,
        argomento=argomento, note=(data.note or "").strip() or None, periodo=periodo, riferimento_periodo=riferimento,
        numero_persone_stimate=persone,
        stato=StatoFabbisognoRichiesta.in_revisione if padre else StatoFabbisognoRichiesta.approvata_hr)
    db.add(unione)
    db.flush()
    autori = {}
    for r in rows:
        r.fusa_in_id = unione.id
        r.stato = StatoFabbisognoRichiesta.fusa
        r.ufficio_in_revisione_presso_id = None
        autori[r.creata_da_id] = r.argomento
    for autore_id, originale in autori.items():
        if autore_id != user.id:
            db.add(Notification(user_id=autore_id, tipo="fabbisogno_unione", link="/fabbisogno",
                                testo=f"La tua richiesta «{originale}» è stata unita ad altre in «{argomento}» da {ufficio.name}: prosegue insieme alle altre."))
    audit_svc.log_from_request(db, request, user, "FABBISOGNO_UNIONE", entity_type="richiesta_fabbisogno", entity_id=str(unione.id), entity_name=argomento,
                                detail=f"{len(rows)} richieste unite presso {ufficio.name}: " + "; ".join(f"{r.argomento} ({r.numero_persone_stimate or 0})" for r in rows))
    db.commit()
    return _serialize_richiesta(unione, db)

@router.post("/richieste/{richiesta_id}/scomponi")
def scomponi_unione(richiesta_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Annulla una fusione finche' nessuno, sopra, l'ha ancora valutata."""
    ctx = _Contesto(db)
    u = ctx.righe.get(uuid.UUID(richiesta_id)) if _e_uuid(richiesta_id) else None
    if not u: raise HTTPException(404)
    if not ctx.figli.get(u.id):
        raise HTTPException(400, "Questa richiesta non è un'unione")
    ufficio = db.query(Group).filter(Group.id == u.ufficio_origine_id).first()
    if not ufficio or str(ufficio.responsabile_id) != str(user.id):
        raise HTTPException(403, "Solo il responsabile che ha fatto l'unione può scomporla")
    padre = ufficio_padre(db, ufficio)
    if u.stato != StatoFabbisognoRichiesta.in_revisione or not padre or u.ufficio_in_revisione_presso_id != padre.id:
        raise HTTPException(400, "L'unione è già stata valutata a un livello superiore: non si può più scomporre")
    for f in ctx.figli[u.id]:
        f.fusa_in_id = None
        f.stato = StatoFabbisognoRichiesta.in_revisione
        f.ufficio_in_revisione_presso_id = ufficio.id
    audit_svc.log_from_request(db, request, user, "FABBISOGNO_SCOMPOSIZIONE", entity_type="richiesta_fabbisogno", entity_id=str(u.id), entity_name=u.argomento,
                                detail=f"unione annullata presso {ufficio.name}: {len(ctx.figli[u.id])} richieste tornano da valutare")
    db.delete(u)
    db.commit()
    return {"ok": True}

def _e_uuid(testo: str) -> bool:
    try:
        uuid.UUID(testo)
        return True
    except ValueError:
        return False

@router.get("/richieste/{richiesta_id}/origine")
def origine_richiesta(richiesta_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Albero di provenienza: da una richiesta unita fino alle richieste originali, con ufficio,
    autore, numeri e note di ciascuna. Lo vede la Formazione, chi ha scritto una delle originali
    e i responsabili degli uffici coinvolti."""
    ctx = _Contesto(db)
    radice = ctx.righe.get(uuid.UUID(richiesta_id)) if _e_uuid(richiesta_id) else None
    if not radice: raise HTTPException(404)

    def nodo(r):
        return {"id": str(r.id), "argomento": r.argomento, "note": r.note, "ufficio_nome": ctx.gruppi.get(r.ufficio_origine_id),
                "creata_da_nome": ctx.utenti.get(r.creata_da_id), "numero_persone_stimate": r.numero_persone_stimate,
                "periodo": r.periodo, "riferimento_periodo": r.riferimento_periodo, "created_at": r.created_at,
                "e_unione": bool(ctx.figli.get(r.id)), "figli": [nodo(f) for f in sorted(ctx.figli.get(r.id, []), key=lambda x: str(ctx.gruppi.get(x.ufficio_origine_id)))]}

    def sottoalbero(r):
        yield r
        for f in ctx.figli.get(r.id, []):
            yield from sottoalbero(f)

    if not user.ha_poteri_formazione:
        mie = {u.id for u in uffici_guidati_da(db, user.id)}
        ammesso = any(n.creata_da_id == user.id or n.ufficio_origine_id in mie or n.ufficio_in_revisione_presso_id in mie for n in sottoalbero(radice))
        if not ammesso:
            raise HTTPException(403, "Non hai accesso alla provenienza di questa richiesta")
    return nodo(radice)

@router.get("/richieste")
def list_richieste_hr(stato: Optional[StatoFabbisognoRichiesta] = None,
                       db: Session = Depends(get_db), user: User = Depends(require_training_admin)):
    q = db.query(FabbisognoRichiesta)
    if stato: q = q.filter(FabbisognoRichiesta.stato == stato)
    else: q = q.filter(FabbisognoRichiesta.stato != StatoFabbisognoRichiesta.fusa)
    rows = q.order_by(FabbisognoRichiesta.created_at.desc()).all()
    ctx = _Contesto(db)
    return [_serialize_richiesta(r, db, ctx) for r in rows]


# --- Richieste formative: la vista della Formazione sulle richieste arrivate ----------------
# Filtrata, ordinabile e paginata lato server: con centinaia di persone e piu' campagne
# l'elenco completo non si legge. Due viste sugli stessi filtri: raggruppata per argomento
# (quante richieste, da quanti uffici, per quante persone) ed elenco dettagliato.

STATI_VISTA = {"arrivate": [StatoFabbisognoRichiesta.approvata_hr], "in_revisione": [StatoFabbisognoRichiesta.in_revisione],
               "rifiutate": [StatoFabbisognoRichiesta.rifiutata],
               "tutte": [StatoFabbisognoRichiesta.in_revisione, StatoFabbisognoRichiesta.approvata_hr, StatoFabbisognoRichiesta.rifiutata]}
ORDINE_DETTAGLIO = {
    "data": lambda r: r["created_at"], "ufficio": lambda r: (r["ufficio_origine_nome"] or "").lower(),
    "argomento": lambda r: r["argomento"].lower(), "persone": lambda r: r["numero_persone_stimate"] if r["numero_persone_stimate"] is not None else -1,
    "periodo": lambda r: str(r["riferimento_periodo"] or (r["periodo"].value if r["periodo"] else "")).lower(),
    "campagna": lambda r: (r["campagna_titolo"] or "~").lower(), "stato": lambda r: str(r["stato"]),
}
ORDINE_RAGGRUPPATO = {"argomento": lambda g: g["argomento"].lower(), "richieste": lambda g: g["richieste"],
                      "uffici": lambda g: g["n_uffici"], "persone": lambda g: g["persone"], "ultima": lambda g: g["ultima"]}


def _normalizza(testo: str) -> str:
    return " ".join((testo or "").lower().split())


def _discendenti(db: Session, ufficio_id: str) -> list:
    ids, frontiera = [ufficio_id], [ufficio_id]
    while frontiera:
        nuovi = [str(f.id) for fid in frontiera for f in uffici_figli(db, fid) if str(f.id) not in ids]
        ids.extend(nuovi)
        frontiera = nuovi
    return ids


def _richieste_filtrate(db: Session, stato, campagna_id, ufficio_id, periodo, q, argomento):
    if stato not in STATI_VISTA:
        raise HTTPException(400, f"Stato non valido: {stato}")
    # Le richieste "fuse" non compaiono mai da sole: conta l'unione che le contiene.
    query = db.query(FabbisognoRichiesta).filter(FabbisognoRichiesta.stato.in_(STATI_VISTA[stato]))
    if campagna_id == "spontanee":
        query = query.filter(FabbisognoRichiesta.campagna_id.is_(None))
    elif campagna_id:
        query = query.filter(FabbisognoRichiesta.campagna_id == campagna_id)
    if periodo:
        query = query.filter(FabbisognoRichiesta.periodo == periodo)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(FabbisognoRichiesta.argomento.ilike(like), FabbisognoRichiesta.note.ilike(like),
                                  FabbisognoRichiesta.riferimento_periodo.ilike(like)))
    ctx = _Contesto(db)
    righe = [_serialize_richiesta(r, db, ctx) for r in query.all()]
    if ufficio_id:
        # l'ufficio filtra sulle richieste ORIGINALI: una unione compare se dentro c'e' qualcuno di quell'area
        area = set(_discendenti(db, ufficio_id))
        righe = [r for r in righe if area & set(r["uffici_origine_ids"])]
    if argomento:
        righe = [r for r in righe if _normalizza(r["argomento"]) == _normalizza(argomento)]
    return righe


def _paginate(elementi, pagina, per_pagina):
    return elementi[(pagina - 1) * per_pagina: pagina * per_pagina]


def _ordina(elementi, chiavi, ordine, direzione, predefinito):
    funzione = chiavi.get(ordine) or chiavi[predefinito]
    return sorted(elementi, key=funzione, reverse=(direzione == "desc"))


@router.get("/richieste-formative")
def richieste_formative(vista: str = "argomento", stato: str = "arrivate", campagna_id: Optional[str] = None, ufficio_id: Optional[str] = None,
                        periodo: Optional[PeriodoFabbisogno] = None, q: Optional[str] = None, argomento: Optional[str] = None,
                        ordine: Optional[str] = None, direzione: str = "desc", pagina: int = 1, per_pagina: int = 25,
                        db: Session = Depends(get_db), user: User = Depends(require_training_admin)):
    pagina, per_pagina = max(1, pagina), min(max(1, per_pagina), 200)
    righe = _richieste_filtrate(db, stato, campagna_id, ufficio_id, periodo, q, argomento)
    riepilogo = {"richieste": len(righe), "argomenti": len({_normalizza(r["argomento"]) for r in righe}),
                 "uffici": len({i for r in righe for i in r["uffici_origine_ids"]}),
                 "persone": sum(r["numero_persone_stimate"] or 0 for r in righe),
                 "richieste_originali": sum(r["n_origini"] for r in righe)}
    if vista == "elenco":
        ordinate = _ordina(righe, ORDINE_DETTAGLIO, ordine, direzione, "data")
        return {"vista": vista, "totale": len(ordinate), "pagina": pagina, "per_pagina": per_pagina,
                "items": _paginate(ordinate, pagina, per_pagina), "riepilogo": riepilogo}
    gruppi = {}
    for r in righe:
        g = gruppi.setdefault(_normalizza(r["argomento"]), {"varianti": {}, "uffici": set(), "persone": 0, "periodi": set(),
                                                             "campagne": set(), "per_campagna": {}, "richieste": 0, "origini": 0, "ultima": r["created_at"]})
        g["varianti"][r["argomento"].strip()] = g["varianti"].get(r["argomento"].strip(), 0) + 1
        g["uffici"].update(r["uffici_origine"])
        g["origini"] = g.get("origini", 0) + r["n_origini"]
        g["persone"] += r["numero_persone_stimate"] or 0
        g["richieste"] += 1
        g["campagne"].add(r["campagna_titolo"] or "Spontanea")
        origine = r["campagna_titolo"] or "Spontanea"
        g["per_campagna"][origine] = g["per_campagna"].get(origine, 0) + (r["numero_persone_stimate"] or 0)
        p = r["riferimento_periodo"] or (r["periodo"].value if hasattr(r["periodo"], "value") else r["periodo"])
        if p:
            g["periodi"].add(p)
        if r["created_at"] and (g["ultima"] is None or r["created_at"] > g["ultima"]):
            g["ultima"] = r["created_at"]
    elenco = [{"chiave": k, "argomento": " ".join(max(g["varianti"], key=lambda v: (g["varianti"][v], v[:1].isupper())).split()), "richieste": g["richieste"],
               "n_uffici": len(g["uffici"]), "uffici": sorted(g["uffici"]), "persone": g["persone"], "richieste_originali": g["origini"],
               "periodi": sorted(g["periodi"]), "campagne": sorted(g["campagne"]), "per_campagna": g["per_campagna"], "ultima": g["ultima"]} for k, g in gruppi.items()]
    ordinate = _ordina(elenco, ORDINE_RAGGRUPPATO, ordine, direzione, "persone")
    return {"vista": "argomento", "totale": len(ordinate), "pagina": pagina, "per_pagina": per_pagina,
            "items": _paginate(ordinate, pagina, per_pagina), "riepilogo": riepilogo}


@router.get("/richieste-formative/export")
def richieste_formative_export(formato: str = "csv", pagina: str = "A4", stato: str = "arrivate", campagna_id: Optional[str] = None,
                               ufficio_id: Optional[str] = None, periodo: Optional[PeriodoFabbisogno] = None, q: Optional[str] = None,
                               ordine: Optional[str] = None, direzione: str = "desc",
                               db: Session = Depends(get_db), user: User = Depends(require_training_admin)):
    """Elenco dettagliato con gli stessi filtri della vista."""
    righe = _ordina(_richieste_filtrate(db, stato, campagna_id, ufficio_id, periodo, q, None), ORDINE_DETTAGLIO, ordine, direzione, "data")
    colonne = ["Ufficio", "Uffici di origine", "Richieste originali", "Argomento", "Periodo", "Riferimento", "N. persone", "Note", "Origine", "Stato", "Inviata da", "Data"]
    dati = [[r["ufficio_origine_nome"], ", ".join(r["uffici_origine"]), r["n_origini"], r["argomento"], r["periodo"].value if hasattr(r["periodo"], "value") else r["periodo"],
             r["riferimento_periodo"], r["numero_persone_stimate"], r["note"], r["campagna_titolo"] or "Spontanea",
             r["stato"].value if hasattr(r["stato"], "value") else r["stato"], r["creata_da_nome"], r["created_at"]] for r in righe]
    return esporta(formato, "richieste_formative", "Richieste formative", colonne, dati, pagina)
