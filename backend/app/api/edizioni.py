from fastapi import APIRouter, Depends, HTTPException, Response, Request, Query
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List
from datetime import datetime
from ..database import get_db
from ..models.edizione import Edizione, EdizioneDocente, ModalitaErogazione, ModalitaCheckin, ModalitaTeams, StatoEdizione, RuoloDocente
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.user import User
from ..models.corso import Corso
from ..services.gerarchia import sottoposti_di
from ..services.etichette import corsi_con_etichette, etichette_del_corso
from ..services.durata import durata_effettiva
from ..services.iscrizioni import crea_iscrizione_con_capacita, promuovi_da_lista_attesa, posti_occupati
from ..services.notifiche import invia_comunicazione_edizione, invia_invito_calendario
from ..services.calendario import evento_edizione, costruisci_ics
from ..models.comunicazione_edizione import ComunicazioneEdizione
from ..services import audit as audit_svc
from .deps import require_training_admin, get_current_user

router = APIRouter(prefix="/api/edizioni", tags=["edizioni"])

_nome_edizione = audit_svc.nome_edizione
_nome_utente = audit_svc.nome_utente

class EdizioneIn(BaseModel):
    corso_id: str
    modalita: ModalitaErogazione
    data_inizio: Optional[datetime] = None
    data_fine: Optional[datetime] = None
    luogo: Optional[str] = None
    posti_max: Optional[int] = None
    lista_attesa_abilitata: bool = False
    checkin_mode: Optional[ModalitaCheckin] = ModalitaCheckin.discente_validato
    teams_mode: Optional[ModalitaTeams] = None
    video_id: Optional[str] = None
    ente_erogatore: Optional[str] = None
    durata_minuti: Optional[int] = None   # vuota = segue il corso; diversa da quella del corso = durata forzata
    sempre_aperta: bool = False           # solo video: senza date, attestato automatico a chi la completa
    note: Optional[str] = None

    @model_validator(mode="after")
    def _sempre_aperta_solo_video(self):
        if self.sempre_aperta:
            if self.modalita != ModalitaErogazione.video:
                raise ValueError("Solo una sessione video può essere sempre disponibile")
            self.data_inizio = self.data_fine = None        # senza date: chi vuole la segue quando vuole
            self.posti_max = None                            # e senza posti contati
            self.lista_attesa_abilitata = False
        return self

    @field_validator("durata_minuti")
    @classmethod
    def _durata_valida(cls, v):
        if v is not None and not 1 <= v <= 100000:
            raise ValueError("La durata deve essere di almeno 1 minuto (e non oltre 100000)")
        return v

    @field_validator("video_id", mode="before")
    @classmethod
    def _stringa_vuota_a_none(cls, v):
        # Il form manda "" quando il campo non è applicabile (es. modalità non video):
        # una stringa vuota non è un UUID valido, va trattata come "nessun valore".
        return v or None

def _durata_propria(db: Session, corso_id, durata) -> Optional[int]:
    """La sessione conserva la durata solo se e' diversa da quella del corso: uguale = segue il corso."""
    if not durata:
        return None
    corso = db.query(Corso).filter(Corso.id == corso_id).first()
    return None if corso is not None and corso.durata_minuti == durata else durata

def _is_docente(edizione: Edizione, user: User) -> bool:
    return any(str(d.user_id) == str(user.id) for d in edizione.docenti)

def _serialize(e: Edizione, db: Session):
    n_iscritti = posti_occupati(db, e.id)
    n_lista_attesa = db.query(Iscrizione).filter(Iscrizione.edizione_id == e.id, Iscrizione.stato == StatoIscrizione.in_lista_attesa).count()
    corso = db.query(Corso).filter(Corso.id == e.corso_id).first()
    nomi = {u.id: u.full_name for u in db.query(User).filter(User.id.in_([d.user_id for d in e.docenti])).all()} if e.docenti else {}
    return {
        "id": str(e.id), "corso_id": str(e.corso_id), "corso_titolo": corso.titolo if corso else None,
        "corso_permetti_autoiscrizione": corso.permetti_autoiscrizione if corso else False,
        "corso_iscrizione_responsabili": corso.iscrizione_responsabili if corso else "solo_formazione",
        "corso_etichette": [{"id": str(x.id), "nome": x.nome, "famiglia": x.famiglia.nome} for x in etichette_del_corso(db, e.corso_id)],
        "modalita": e.modalita, "stato": e.stato,
        "data_inizio": e.data_inizio, "data_fine": e.data_fine, "luogo": e.luogo,
        "posti_max": e.posti_max, "lista_attesa_abilitata": e.lista_attesa_abilitata, "n_lista_attesa": n_lista_attesa,
        "checkin_mode": e.checkin_mode, "teams_mode": e.teams_mode,
        "teams_join_url": e.teams_join_url, "video_id": str(e.video_id) if e.video_id else None,
        "ente_erogatore": e.ente_erogatore, "sempre_aperta": e.sempre_aperta,
        "durata_minuti": e.durata_minuti, "durata_corso_minuti": corso.durata_minuti if corso else None,
        "durata_effettiva_minuti": durata_effettiva(e, corso),
        "durata_modificata": bool(e.durata_minuti and corso and corso.durata_minuti and e.durata_minuti != corso.durata_minuti),
        "note": e.note,
        "chiusa_at": e.chiusa_at, "n_iscritti": n_iscritti,
        "docenti": [{"user_id": str(d.user_id), "ruolo": d.ruolo, "nome": nomi.get(d.user_id)} for d in e.docenti],
    }

@router.get("")
def list_edizioni(corso_id: Optional[str] = None, mie_come_docente: bool = False, etichette: Optional[List[str]] = Query(None),
                   db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = db.query(Edizione).options(joinedload(Edizione.docenti))
    if corso_id: q = q.filter(Edizione.corso_id == corso_id)
    ammessi = corsi_con_etichette(db, etichette)
    if ammessi is not None:
        q = q.filter(Edizione.corso_id.in_(ammessi or [None]))
    if mie_come_docente:
        q = q.join(EdizioneDocente, EdizioneDocente.edizione_id == Edizione.id).filter(EdizioneDocente.user_id == user.id)
    return [_serialize(e, db) for e in q.order_by(Edizione.data_inizio.desc().nullslast()).all()]

@router.get("/mie/iscrizioni")
def mie_iscrizioni(db: Session = Depends(get_db), user=Depends(get_current_user)):
    # Le iscrizioni annullate non sono piu' mie: non compaiono in «I miei corsi» ne' nello storico (restano nel registro attivita')
    rows = db.query(Iscrizione).filter(Iscrizione.user_id == user.id, Iscrizione.stato != StatoIscrizione.annullato).all()
    out = []
    for i in rows:
        e = db.query(Edizione).filter(Edizione.id == i.edizione_id).first()
        corso = db.query(Corso).filter(Corso.id == e.corso_id).first() if e else None
        aggiornamento = None
        if i.stato == StatoIscrizione.completato and corso:
            if i.versione_corso is None or i.versione_corso < corso.versione_minima_valida:
                aggiornamento = "richiesto"
            elif i.versione_corso < corso.versione:
                aggiornamento = "disponibile"
        out.append({
            "id": str(i.id), "edizione_id": str(i.edizione_id), "stato": i.stato,
            "completato_at": i.completato_at, "ripeti_entro": i.ripeti_entro,
            "corso_titolo": corso.titolo if corso else None,
            "corso_validita_mesi": corso.validita_mesi if corso else None,
            "edizione_modalita": e.modalita if e else None,
            "edizione_stato": e.stato if e else None,
            "edizione_data_inizio": e.data_inizio if e else None,
            "edizione_sempre_aperta": bool(e and e.sempre_aperta),
            "aggiornamento_contenuto": aggiornamento,
        })
    return out

@router.get("/{edizione_id}")
def get_edizione(edizione_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    e = db.query(Edizione).options(joinedload(Edizione.docenti)).filter(Edizione.id == edizione_id).first()
    if not e: raise HTTPException(404)
    return _serialize(e, db)

@router.post("")
def create_edizione(data: EdizioneIn, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    campi = data.model_dump()
    campi["durata_minuti"] = _durata_propria(db, data.corso_id, data.durata_minuti)
    e = Edizione(**campi, stato=StatoEdizione.bozza)
    db.add(e); db.flush()
    audit_svc.log_from_request(db, request, user, "CREATE", entity_type="edizione", entity_id=str(e.id), entity_name=_nome_edizione(db, e))
    db.commit(); db.refresh(e)
    return _serialize(e, db)

@router.put("/{edizione_id}")
def update_edizione(edizione_id: str, data: EdizioneIn, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    e = db.query(Edizione).options(joinedload(Edizione.docenti)).filter(Edizione.id == edizione_id).first()
    if not e: raise HTTPException(404)
    if e.stato == StatoEdizione.chiusa:
        raise HTTPException(400, "Edizione chiusa: non modificabile")
    for k, v in data.model_dump().items(): setattr(e, k, v)
    e.durata_minuti = _durata_propria(db, data.corso_id, data.durata_minuti)
    db.flush()
    promossi = []
    while True:  # se ora ci sono posti liberi, chi era in lista d'attesa sale (in ordine di arrivo)
        p = promuovi_da_lista_attesa(db, edizione_id)
        if not p:
            break
        db.flush()
        promossi.append(p)
    audit_svc.log_from_request(db, request, user, "UPDATE", entity_type="edizione", entity_id=str(e.id), entity_name=_nome_edizione(db, e),
                                detail=f"promossi dalla lista d'attesa: {len(promossi)}" if promossi else None)
    db.commit()
    if e.data_inizio:
        for p in promossi:
            invia_invito_calendario(db, e, p.user_id)
    return _serialize(e, db)

@router.post("/{edizione_id}/pianifica")
def pianifica_edizione(edizione_id: str, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    e = db.query(Edizione).filter(Edizione.id == edizione_id).first()
    if not e: raise HTTPException(404)
    if e.stato == StatoEdizione.pianificata:
        return {"ok": True}  # gia' pianificata: nessun nuovo invito agli iscritti
    if e.stato != StatoEdizione.bozza:
        raise HTTPException(400, "Si pianifica solo una sessione in bozza")
    e.stato = StatoEdizione.pianificata
    audit_svc.log_from_request(db, request, user, "PIANIFICA", entity_type="edizione", entity_id=str(e.id), entity_name=_nome_edizione(db, e))
    db.commit()
    # Chi era già iscritto prima che la data fosse confermata riceve solo ora
    # l'invito calendario - chi si iscrive dopo lo riceve subito (vedi iscrivi()).
    if e.data_inizio:
        for i in db.query(Iscrizione).filter(Iscrizione.edizione_id == edizione_id, Iscrizione.stato == StatoIscrizione.iscritto).all():
            invia_invito_calendario(db, e, i.user_id)
    return {"ok": True}

@router.get("/{edizione_id}/calendario.ics")
def calendario_ics(edizione_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    e = db.query(Edizione).filter(Edizione.id == edizione_id).first()
    if not e: raise HTTPException(404)
    corso = db.query(Corso).filter(Corso.id == e.corso_id).first()
    evento = evento_edizione(e, corso.titolo if corso else "Sessione formativa")
    if not evento:
        raise HTTPException(400, "Questa sessione non ha ancora una data fissata")
    ics = costruisci_ics([evento])
    return Response(content=ics, media_type="text/calendar; charset=utf-8",
                     headers={"Content-Disposition": 'attachment; filename="sessione.ics"'})

# --- Docenti ---

class DocenteIn(BaseModel):
    user_id: str
    ruolo: RuoloDocente = RuoloDocente.titolare

@router.post("/{edizione_id}/docenti")
def aggiungi_docente(edizione_id: str, data: DocenteIn, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    e = db.query(Edizione).filter(Edizione.id == edizione_id).first()
    if not e: raise HTTPException(404)
    esiste = db.query(EdizioneDocente).filter(EdizioneDocente.edizione_id == edizione_id, EdizioneDocente.user_id == data.user_id).first()
    if esiste: raise HTTPException(400, "Già docente su questa edizione")
    docente = db.query(User).filter(User.id == data.user_id, User.is_active == True).first()  # noqa: E712
    if not docente: raise HTTPException(404, "Persona non trovata")
    if not docente.puo_essere_docente:
        raise HTTPException(400, "Questa persona non è abilitata come Docente: abilita la qualifica Docente dalla sua scheda utente")
    db.add(EdizioneDocente(edizione_id=edizione_id, user_id=data.user_id, ruolo=data.ruolo))
    audit_svc.log_from_request(db, request, user, "ASSIGN_DOCENTE", entity_type="edizione", entity_id=str(e.id),
                                entity_name=_nome_edizione(db, e), detail=f"docente: {_nome_utente(db, data.user_id)} ({data.ruolo.value})")
    db.commit()
    return {"ok": True}

@router.delete("/{edizione_id}/docenti/{user_id}")
def rimuovi_docente(edizione_id: str, user_id: str, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    db.query(EdizioneDocente).filter(EdizioneDocente.edizione_id == edizione_id, EdizioneDocente.user_id == user_id).delete()
    e = db.query(Edizione).filter(Edizione.id == edizione_id).first()
    audit_svc.log_from_request(db, request, user, "UNASSIGN_DOCENTE", entity_type="edizione", entity_id=edizione_id,
                                entity_name=_nome_edizione(db, e) if e else None, detail=f"docente: {_nome_utente(db, user_id)}")
    db.commit()
    return {"ok": True}

# --- Iscrizioni ---

@router.get("/{edizione_id}/iscrizioni")
def list_iscrizioni(edizione_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(Iscrizione).options(joinedload(Iscrizione.evidenze)).filter(Iscrizione.edizione_id == edizione_id).all()
    out = []
    for i in rows:
        u = db.query(User).filter(User.id == i.user_id).first()
        out.append({
            "id": str(i.id), "user_id": str(i.user_id),
            "user_full_name": u.full_name if u else None,
            "stato": i.stato,
            "n_evidenze": len(i.evidenze),
        })
    return out

@router.post("/{edizione_id}/iscrizioni")
def iscrivi(edizione_id: str, user_ids: List[str], request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    e = db.query(Edizione).filter(Edizione.id == edizione_id).first()
    if not e: raise HTTPException(404)
    e_formazione = user.ha_poteri_formazione
    if e.stato in (StatoEdizione.chiusa, StatoEdizione.annullata):
        raise HTTPException(400, "La sessione è chiusa o annullata: non si iscrive più nessuno")
    if not e_formazione and e.stato == StatoEdizione.bozza:
        raise HTTPException(400, "La sessione non è ancora pianificata")
    if not e_formazione:
        # Non Ufficio Formazione: può iscrivere solo i propri sottoposti (gerarchia
        # uffici, sezione L), mai altri - stessa autorizzazione derivata, nessun
        # campo "posso iscrivere" da mantenere a parte.
        corso = db.query(Corso).filter(Corso.id == e.corso_id).first()
        modo = corso.iscrizione_responsabili if corso else "solo_formazione"
        if modo == "su_richiesta":
            raise HTTPException(403, "A questo corso non si iscrive direttamente: chiedi l'iscrizione alla Formazione (dalla pagina «Il mio team»)")
        if modo != "diretta":     # elenco ammesso: qualunque altro valore (anche sconosciuto) lascia il corso chiuso
            raise HTTPException(403, "A questo corso iscrive solo la Formazione")
        sottoposti_ids = {str(s.id) for s in sottoposti_di(db, user.id)}
        non_autorizzati = [uid for uid in user_ids if uid not in sottoposti_ids]
        if non_autorizzati:
            raise HTTPException(403, "Puoi iscrivere solo le persone sotto la tua responsabilità")
    creati = []
    confermati = []
    esclusi = []
    for uid in user_ids:
        esiste = db.query(Iscrizione).filter(Iscrizione.edizione_id == edizione_id, Iscrizione.user_id == uid,
                                              Iscrizione.stato != StatoIscrizione.annullato).first()
        if esiste: continue
        try:
            i = crea_iscrizione_con_capacita(db, e, uid)
        except HTTPException as ex:  # posti finiti: questa persona no, le altre gia' iscritte restano
            esclusi.append({"user_id": uid, "motivo": ex.detail})
            continue
        db.flush()  # il conteggio dei posti per la persona successiva deve vedere questa
        creati.append(uid)
        if i.stato == StatoIscrizione.iscritto:
            confermati.append(uid)
        audit_svc.log_from_request(db, request, user, "ENROLL", entity_type="edizione", entity_id=edizione_id,
                                    entity_name=_nome_edizione(db, e),
                                    detail=f"utente: {_nome_utente(db, uid)} - stato: {i.stato.value}")
    db.commit()
    # Solo a chi ha un posto confermato, non a chi finisce in lista d'attesa
    # (nessuna data da segnare finché non viene promosso, vedi annulla_iscrizione).
    if e.data_inizio:
        for uid in confermati:
            invia_invito_calendario(db, e, uid)
    return {"ok": True, "iscritti": creati, "non_iscritti": esclusi}

@router.post("/{edizione_id}/iscrizioni/{iscrizione_id}/annulla")
def annulla_iscrizione(edizione_id: str, iscrizione_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    i = db.query(Iscrizione).filter(Iscrizione.id == iscrizione_id, Iscrizione.edizione_id == edizione_id).first()
    if not i: raise HTTPException(404)
    e_admin = user.ha_poteri_formazione
    e_se_stesso = str(i.user_id) == str(user.id)
    e_responsabile_suo = str(i.user_id) in {str(s.id) for s in sottoposti_di(db, user.id)}
    if not (e_admin or e_se_stesso or e_responsabile_suo):
        raise HTTPException(403, "Non puoi annullare questa iscrizione")
    if i.stato not in (StatoIscrizione.iscritto, StatoIscrizione.in_lista_attesa):
        # un'iscrizione gia' completata o chiusa e' storico di compliance, non si "annulla"
        raise HTTPException(400, "Si possono annullare solo le iscrizioni in corso o in lista d'attesa")
    occupava_posto = i.stato == StatoIscrizione.iscritto
    i.stato = StatoIscrizione.annullato
    db.flush()
    e = db.query(Edizione).filter(Edizione.id == edizione_id).first()
    promosso = None
    if e and e.lista_attesa_abilitata and occupava_posto:  # chi era in lista non libera nessun posto
        promosso = promuovi_da_lista_attesa(db, edizione_id)
    detail = f"utente: {_nome_utente(db, i.user_id)}"
    if promosso:
        detail += f" - promosso da lista d'attesa: {_nome_utente(db, promosso.user_id)}"
    audit_svc.log_from_request(db, request, user, "CANCEL_ENROLLMENT", entity_type="edizione", entity_id=edizione_id,
                                entity_name=_nome_edizione(db, e) if e else None, detail=detail)
    db.commit()
    if promosso and e.data_inizio:
        invia_invito_calendario(db, e, promosso.user_id)
    return {"ok": True}

# --- Comunicazioni ---

class ComunicazioneIn(BaseModel):
    oggetto: str
    messaggio: str

def _autorizzato_comunicazione(e: Edizione, user: User) -> bool:
    return _is_docente(e, user) or user.ha_poteri_formazione

@router.post("/{edizione_id}/comunicazione")
def invia_comunicazione(edizione_id: str, data: ComunicazioneIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    e = db.query(Edizione).options(joinedload(Edizione.docenti)).filter(Edizione.id == edizione_id).first()
    if not e: raise HTTPException(404)
    if not _autorizzato_comunicazione(e, user):
        raise HTTPException(403, "Non autorizzato a inviare comunicazioni per questa sessione")
    destinatari = [i.user_id for i in db.query(Iscrizione).filter(
        Iscrizione.edizione_id == edizione_id,
        Iscrizione.stato.in_([StatoIscrizione.iscritto, StatoIscrizione.in_lista_attesa]),
    ).all()]
    n = invia_comunicazione_edizione(db, destinatari, data.oggetto, data.messaggio, link=f"/sessioni/{edizione_id}")
    db.add(ComunicazioneEdizione(edizione_id=edizione_id, mittente_id=user.id, oggetto=data.oggetto,
                                  messaggio=data.messaggio, n_destinatari=n))
    audit_svc.log_from_request(db, request, user, "SEND_COMMUNICATION", entity_type="edizione", entity_id=edizione_id,
                                entity_name=_nome_edizione(db, e), detail=f"oggetto: {data.oggetto} - destinatari: {n}")
    db.commit()
    return {"ok": True, "inviati": n}

@router.get("/{edizione_id}/comunicazioni")
def list_comunicazioni(edizione_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    e = db.query(Edizione).options(joinedload(Edizione.docenti)).filter(Edizione.id == edizione_id).first()
    if not e: raise HTTPException(404)
    if not _autorizzato_comunicazione(e, user):
        raise HTTPException(403, "Non autorizzato")
    righe = db.query(ComunicazioneEdizione).filter(ComunicazioneEdizione.edizione_id == edizione_id)\
        .order_by(ComunicazioneEdizione.created_at.desc()).all()
    out = []
    for r in righe:
        mittente = db.query(User).filter(User.id == r.mittente_id).first() if r.mittente_id else None
        out.append({
            "id": str(r.id), "oggetto": r.oggetto, "messaggio": r.messaggio,
            "n_destinatari": r.n_destinatari, "mittente": mittente.full_name if mittente else None,
            "created_at": r.created_at,
        })
    return out

@router.post("/{edizione_id}/duplica")
def duplica_edizione(edizione_id: str, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    orig = db.query(Edizione).options(joinedload(Edizione.docenti)).filter(Edizione.id == edizione_id).first()
    if not orig: raise HTTPException(404)
    nuova = Edizione(
        corso_id=orig.corso_id, modalita=orig.modalita, stato=StatoEdizione.bozza,
        luogo=orig.luogo, posti_max=orig.posti_max, lista_attesa_abilitata=orig.lista_attesa_abilitata,
        checkin_mode=orig.checkin_mode, teams_mode=orig.teams_mode,
        video_id=orig.video_id, ente_erogatore=orig.ente_erogatore,
        # di una sessione chiusa la durata e' congelata (anche se era solo quella del corso): la copia riparte dal corso
        durata_minuti=None if orig.stato == StatoEdizione.chiusa else orig.durata_minuti,
        sempre_aperta=orig.sempre_aperta,
        note=orig.note,
    )
    db.add(nuova); db.flush()
    for d in orig.docenti:
        db.add(EdizioneDocente(edizione_id=nuova.id, user_id=d.user_id, ruolo=d.ruolo))
    audit_svc.log_from_request(db, request, user, "CREATE", entity_type="edizione", entity_id=str(nuova.id),
                                entity_name=_nome_edizione(db, nuova), detail=f"duplicata da {edizione_id}")
    db.commit(); db.refresh(nuova)
    return _serialize(nuova, db)
