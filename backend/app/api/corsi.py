import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List
from ..database import get_db
from ..models.corso import Corso, AzioneTestNonSuperato, MODI_ISCRIZIONE_RESPONSABILI
from ..models.edizione import Edizione
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.user import User
from ..services.notifiche import _crea_se_assente, _escalation_responsabili
from ..services import audit as audit_svc
from ..services import etichette as etichette_svc
from ..services import elimina_corso as elimina_corso_svc
from .deps import require_training_admin, require_admin_tecnico, get_current_user

router = APIRouter(prefix="/api/corsi", tags=["corsi"])

class CorsoIn(BaseModel):
    titolo: str
    descrizione: Optional[str] = None
    categoria: Optional[str] = None
    validita_mesi: Optional[int] = None
    durata_minuti: Optional[int] = None   # quanto dura il corso (le sessioni la ereditano)
    iscrizione_responsabili: str = "solo_formazione"   # chi puo' iscrivere oltre alla Formazione: nessuno / i responsabili / i responsabili su richiesta
    ha_test_finale: bool = False
    azione_test_non_superato: AzioneTestNonSuperato = AzioneTestNonSuperato.concludi_comunque
    giorni_scadenza_breve: Optional[int] = None
    confronta_pre_post_test: bool = False
    permetti_autoiscrizione: bool = False
    richiedi_approvazione_responsabile: bool = False
    certificato_template_id: Optional[str] = None
    rinnovo_automatico: bool = False
    rinnovo_giorni_anticipo: int = 30
    is_active: bool = True
    etichette: Optional[List[str]] = None  # None = non toccare le etichette (es. cambio del solo template)
    questionario_gradimento_id: Optional[str] = None   # vuoto = il questionario predefinito; non indicato in una modifica = non toccarlo

    @field_validator("questionario_gradimento_id", mode="before")
    @classmethod
    def _questionario_vuoto(cls, v):
        return v or None

    @model_validator(mode="after")
    def _rinnovo_coerente(self):
        if self.iscrizione_responsabili not in MODI_ISCRIZIONE_RESPONSABILI:
            raise ValueError("Modo di iscrizione dei responsabili non valido")
        if self.durata_minuti is not None and not 1 <= self.durata_minuti <= 100000:
            raise ValueError("La durata deve essere di almeno 1 minuto (e non oltre 100000)")
        if self.rinnovo_automatico and not self.validita_mesi:
            raise ValueError("Il rinnovo automatico richiede una validità del corso (mesi)")
        if not 1 <= self.rinnovo_giorni_anticipo <= 365:
            raise ValueError("I giorni di anticipo devono essere tra 1 e 365")
        return self

class NuovaVersioneIn(BaseModel):
    richiedi_ripetizione: bool = False
    nota: Optional[str] = None

def _controlla_questionario(db: Session, questionario_id):
    if questionario_id:
        from ..models.questionario import QuestionarioGradimento
        try:
            uuid.UUID(str(questionario_id))
        except ValueError:
            raise HTTPException(400, "Questionario di gradimento non trovato")
        esiste = db.query(QuestionarioGradimento).filter(QuestionarioGradimento.id == questionario_id).first()
        if not esiste:
            raise HTTPException(400, "Questionario di gradimento non trovato")

def _serialize(c: Corso, db: Session = None, famiglie=None):
    extra = etichette_svc.descrivi(db, c, famiglie) if db is not None else {}
    return {**extra, "id": str(c.id), "titolo": c.titolo, "descrizione": c.descrizione,
            "categoria": c.categoria, "validita_mesi": c.validita_mesi, "durata_minuti": c.durata_minuti,
            "iscrizione_responsabili": c.iscrizione_responsabili,
            "ha_test_finale": c.ha_test_finale,
            "azione_test_non_superato": c.azione_test_non_superato,
            "giorni_scadenza_breve": c.giorni_scadenza_breve,
            "confronta_pre_post_test": c.confronta_pre_post_test,
            "permetti_autoiscrizione": c.permetti_autoiscrizione,
            "richiedi_approvazione_responsabile": c.richiedi_approvazione_responsabile,
            "certificato_template_id": str(c.certificato_template_id) if c.certificato_template_id else None,
            "questionario_gradimento_id": str(c.questionario_gradimento_id) if c.questionario_gradimento_id else None,
            "rinnovo_automatico": c.rinnovo_automatico, "rinnovo_giorni_anticipo": c.rinnovo_giorni_anticipo,
            "versione": c.versione, "versione_minima_valida": c.versione_minima_valida,
            "is_active": c.is_active, "created_at": c.created_at}

@router.get("")
def list_corsi(db: Session = Depends(get_db), user=Depends(get_current_user)):
    from ..models.etichetta import EtichettaFamiglia
    famiglie = db.query(EtichettaFamiglia).filter(EtichettaFamiglia.archiviata == False).all()  # noqa: E712
    return [_serialize(c, db, famiglie) for c in db.query(Corso).order_by(Corso.titolo).all()]

@router.get("/{corso_id}")
def get_corso(corso_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = db.query(Corso).filter(Corso.id == corso_id).first()
    if not c: raise HTTPException(404)
    return _serialize(c, db)

@router.post("")
def create_corso(data: CorsoIn, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    _controlla_questionario(db, data.questionario_gradimento_id)
    c = Corso(**data.model_dump(exclude={"etichette"}))
    db.add(c); db.flush()
    try:
        etichette_svc.imposta_etichette(db, c, data.etichette or [])
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    audit_svc.log_from_request(db, request, user, "CREATE", entity_type="corso", entity_id=str(c.id), entity_name=c.titolo)
    db.commit(); db.refresh(c)
    return _serialize(c, db)

@router.put("/{corso_id}")
def update_corso(corso_id: str, data: CorsoIn, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    c = db.query(Corso).filter(Corso.id == corso_id).first()
    if not c: raise HTTPException(404)
    _controlla_questionario(db, data.questionario_gradimento_id)
    escludi = {"etichette"} | (set() if "questionario_gradimento_id" in data.model_fields_set else {"questionario_gradimento_id"})
    for k, v in data.model_dump(exclude=escludi).items(): setattr(c, k, v)
    if data.etichette is not None:
        try:
            etichette_svc.imposta_etichette(db, c, data.etichette)
        except ValueError as e:
            db.rollback()
            raise HTTPException(400, str(e))
    audit_svc.log_from_request(db, request, user, "UPDATE", entity_type="corso", entity_id=str(c.id), entity_name=c.titolo)
    db.commit()
    return _serialize(c, db)

@router.get("/{corso_id}/rinnovo/anteprima")
def anteprima_rinnovo(corso_id: str, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    """Chi verrebbe iscritto al prossimo giro e a quale sessione, senza modificare nulla."""
    from ..services.rinnovo import anteprima
    c = db.query(Corso).filter(Corso.id == corso_id).first()
    if not c: raise HTTPException(404)
    return anteprima(db, c)

@router.post("/{corso_id}/nuova-versione")
def nuova_versione(corso_id: str, data: NuovaVersioneIn, request: Request,
                    db: Session = Depends(get_db), user=Depends(require_training_admin)):
    """Azione esplicita e separata dalla normale modifica del corso (mai un
    bump automatico su un editing qualsiasi): segna che il contenuto è
    cambiato. Se richiedi_ripetizione è spuntato, chi ha già completato il
    corso con una versione precedente non è più compliant e viene notificato
    (con escalation al responsabile); altrimenti resta compliant e vede solo
    un'etichetta informativa "aggiornamento disponibile" - decisione
    volutamente manuale corso per corso, mai scattata in automatico su tutti
    i corsi (con 500+ utenti l'impatto di un bump non pensato sarebbe pesante)."""
    c = db.query(Corso).filter(Corso.id == corso_id).first()
    if not c: raise HTTPException(404)

    c.versione += 1
    if data.richiedi_ripetizione:
        c.versione_minima_valida = c.versione
    db.flush()

    notificati = 0
    if data.richiedi_ripetizione:
        interessati = (
            db.query(Iscrizione)
            .join(Edizione, Iscrizione.edizione_id == Edizione.id)
            .filter(Edizione.corso_id == corso_id, Iscrizione.stato == StatoIscrizione.completato)
            .filter((Iscrizione.versione_corso.is_(None)) | (Iscrizione.versione_corso < c.versione_minima_valida))
            .all()
        )
        testo = f"Il corso \"{c.titolo}\" è stato aggiornato: la versione che hai seguito non è più valida, va ripetuto."
        for i in interessati:
            discente = db.query(User).filter(User.id == i.user_id).first()
            if not discente:
                continue
            dedup_key = f"versione_corso:{c.id}:{c.versione_minima_valida}:{i.user_id}"
            if _crea_se_assente(db, i.user_id, "versione_corso", testo, dedup_key=dedup_key):
                notificati += 1
            notificati += _escalation_responsabili(db, discente, "versione_corso", testo, dedup_key)

    audit_svc.log_from_request(db, request, user, "UPDATE", entity_type="corso", entity_id=str(c.id),
                                entity_name=c.titolo,
                                detail=f"Nuova versione {c.versione} (richiedi_ripetizione={data.richiedi_ripetizione})" + (f" - {data.nota}" if data.nota else ""))
    db.commit()
    return {"versione": c.versione, "versione_minima_valida": c.versione_minima_valida, "notificati": notificati}

class EliminaCorsoIn(BaseModel):
    conferma: str       # il titolo del corso, scritto per intero: nessuna eliminazione per sbaglio


@router.get("/{corso_id}/eliminazione")
def esame_eliminazione(corso_id: str, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    """Cosa succederebbe eliminando il corso (solo admin tecnico): se si puo' e che cosa verrebbe tolto."""
    c = db.query(Corso).filter(Corso.id == corso_id).first()
    if not c: raise HTTPException(404)
    return elimina_corso_svc.esame(db, c)


@router.post("/{corso_id}/elimina")
def elimina_corso(corso_id: str, data: EliminaCorsoIn, request: Request, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    """Eliminazione definitiva: solo admin tecnico, solo se il corso non ha lasciato tracce di formazione, e solo
    scrivendo il titolo. Altrimenti il corso si disattiva (resta lo storico)."""
    c = db.query(Corso).filter(Corso.id == corso_id).first()
    if not c: raise HTTPException(404)
    if data.conferma.strip() != c.titolo.strip():
        raise HTTPException(400, "Per confermare scrivi il titolo del corso esattamente com'è")
    esito = elimina_corso_svc.esame(db, c)
    if not esito["eliminabile"]:
        raise HTTPException(409, "Il corso non si può eliminare (" + "; ".join(esito["motivi"]) + "): disattivalo, così resta lo storico")
    titolo, cid = c.titolo, str(c.id)
    try:
        elimina_corso_svc.elimina(db, c)
        audit_svc.log_from_request(db, request, user, "DELETE", entity_type="corso", entity_id=cid, entity_name=titolo,
                                    detail=f"eliminato definitivamente (sessioni: {esito['sessioni']}, test: {esito['test']})")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Il corso ha dati collegati che non si possono togliere: disattivalo, così resta lo storico")
    return {"ok": True}


@router.delete("/{corso_id}")
def delete_corso(corso_id: str, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    c = db.query(Corso).filter(Corso.id == corso_id).first()
    if not c: raise HTTPException(404)
    c.is_active = False
    audit_svc.log_from_request(db, request, user, "DELETE", entity_type="corso", entity_id=str(c.id), entity_name=c.titolo, detail="disattivato")
    db.commit()
    return {"ok": True}
