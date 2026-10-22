import csv, io
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import Optional, List, Dict
from ..database import get_db
from ..models.test import Test, Domanda, OpzioneRisposta, TentativoTest, MomentoTest
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.edizione import Edizione, EdizioneDocente, StatoEdizione
from ..models.corso import Corso
from ..models.user import User
from ..services import certificati as cert_svc
from ..services import audit as audit_svc
from ..services.completamento import completa_se_dovuto
from ..services.percorsi_iscrizioni import avanza_e_invita
from ..services.export import neutralizza
from .deps import get_current_user, require_training_admin

router = APIRouter(tags=["test"])

def _puo_gestire_test(db: Session, user: User, corso_id: str) -> bool:
    """Creazione/modifica test riservata a Ufficio Formazione/Admin o a un
    Docente che ha effettivamente insegnato questo corso (docente di
    almeno un'edizione pianificata o in corso) - mai all'assistente, sempre un umano autorizzato."""
    if user.ha_poteri_formazione:
        return True
    return db.query(EdizioneDocente).join(Edizione, Edizione.id == EdizioneDocente.edizione_id).filter(
        Edizione.corso_id == corso_id, EdizioneDocente.user_id == user.id,
        Edizione.stato.in_((StatoEdizione.pianificata, StatoEdizione.in_corso))).first() is not None

class OpzioneIn(BaseModel):
    testo: str
    corretta: bool = False

class DomandaIn(BaseModel):
    testo: str
    ordine: int = 0
    opzioni: List[OpzioneIn]

class TestIn(BaseModel):
    titolo: str
    momento: MomentoTest = MomentoTest.finale
    soglia_superamento_pct: float = 60.0
    tentativi_max: Optional[int] = None
    domande: List[DomandaIn] = []

def _serialize(t: Test, include_corrette: bool):
    return {
        "id": str(t.id), "corso_id": str(t.corso_id), "titolo": t.titolo, "momento": t.momento,
        "soglia_superamento_pct": t.soglia_superamento_pct, "tentativi_max": t.tentativi_max,
        "domande": [{
            "id": str(d.id), "testo": d.testo, "ordine": d.ordine,
            "opzioni": [{"id": str(o.id), "testo": o.testo, **({"corretta": o.corretta} if include_corrette else {})}
                        for o in d.opzioni],
        } for d in sorted(t.domande, key=lambda x: x.ordine)],
    }

@router.get("/api/corsi/{corso_id}/test")
def list_test_corso(corso_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # chi puo' modificare il test deve vedere le risposte corrette, altrimenti salvandolo le perderebbe
    is_admin = _puo_gestire_test(db, user, corso_id)
    rows = db.query(Test).options(joinedload(Test.domande).joinedload(Domanda.opzioni)).filter(Test.corso_id == corso_id).all()
    return [_serialize(t, is_admin) for t in rows]

@router.get("/api/test/{test_id}")
def get_test(test_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    t = db.query(Test).options(joinedload(Test.domande).joinedload(Domanda.opzioni)).filter(Test.id == test_id).first()
    if not t: raise HTTPException(404)
    return _serialize(t, _puo_gestire_test(db, user, str(t.corso_id)))

@router.post("/api/corsi/{corso_id}/test")
def create_test(corso_id: str, data: TestIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    corso = db.query(Corso).filter(Corso.id == corso_id).first()
    if not corso: raise HTTPException(404, "Corso non trovato")
    if not _puo_gestire_test(db, user, corso_id):
        raise HTTPException(403, "Riservato a chi ha il permesso Formazione o a un Docente che insegna questo corso")
    t = Test(corso_id=corso_id, titolo=data.titolo, momento=data.momento,
              soglia_superamento_pct=data.soglia_superamento_pct, tentativi_max=data.tentativi_max)
    db.add(t); db.flush()
    for i, d in enumerate(data.domande):
        dom = Domanda(test_id=t.id, testo=d.testo, ordine=d.ordine or i)
        db.add(dom); db.flush()
        for o in d.opzioni:
            db.add(OpzioneRisposta(domanda_id=dom.id, testo=o.testo, corretta=o.corretta))
    db.commit()
    t = db.query(Test).options(joinedload(Test.domande).joinedload(Domanda.opzioni)).filter(Test.id == t.id).first()
    return _serialize(t, True)

@router.put("/api/test/{test_id}")
def update_test(test_id: str, data: TestIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(Test).filter(Test.id == test_id).first()
    if not t: raise HTTPException(404)
    if not _puo_gestire_test(db, user, str(t.corso_id)):
        raise HTTPException(403, "Riservato a chi ha il permesso Formazione o a un Docente che insegna questo corso")
    t.titolo = data.titolo; t.momento = data.momento
    t.soglia_superamento_pct = data.soglia_superamento_pct; t.tentativi_max = data.tentativi_max
    # Sostituzione completa delle domande: autoring è admin-only e poco frequente,
    # più semplice che fare un diff fine.
    vecchie = [d.id for d in db.query(Domanda.id).filter(Domanda.test_id == t.id).all()]
    if vecchie:  # prima le opzioni: la cancellazione in blocco non segue le cascate dell'ORM
        db.query(OpzioneRisposta).filter(OpzioneRisposta.domanda_id.in_(vecchie)).delete(synchronize_session=False)
    db.query(Domanda).filter(Domanda.test_id == t.id).delete(synchronize_session=False)
    db.flush()
    for i, d in enumerate(data.domande):
        dom = Domanda(test_id=t.id, testo=d.testo, ordine=d.ordine or i)
        db.add(dom); db.flush()
        for o in d.opzioni:
            db.add(OpzioneRisposta(domanda_id=dom.id, testo=o.testo, corretta=o.corretta))
    db.commit()
    t = db.query(Test).options(joinedload(Test.domande).joinedload(Domanda.opzioni)).filter(Test.id == t.id).first()
    return _serialize(t, True)

@router.delete("/api/test/{test_id}")
def delete_test(test_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(Test).filter(Test.id == test_id).first()
    if not t: raise HTTPException(404)
    if not _puo_gestire_test(db, user, str(t.corso_id)):
        raise HTTPException(403, "Riservato a chi ha il permesso Formazione o a un Docente che insegna questo corso")
    db.delete(t); db.commit()
    return {"ok": True}

# --- Svolgimento ---

class TentativoIn(BaseModel):
    iscrizione_id: str
    risposte: Dict[str, str]  # domanda_id -> opzione_id

@router.post("/api/test/{test_id}/tenta")
def tenta_test(test_id: str, data: TentativoIn, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    t = db.query(Test).options(joinedload(Test.domande).joinedload(Domanda.opzioni)).filter(Test.id == test_id).first()
    if not t: raise HTTPException(404)
    iscr = db.query(Iscrizione).filter(Iscrizione.id == data.iscrizione_id).first()
    if not iscr or str(iscr.user_id) != str(user.id):
        raise HTTPException(403, "Iscrizione non valida per l'utente corrente")
    edizione = db.query(Edizione).filter(Edizione.id == iscr.edizione_id).first()
    if not edizione or str(edizione.corso_id) != str(t.corso_id):
        raise HTTPException(400, "Il test non appartiene al corso di questa iscrizione")

    n_precedenti = db.query(TentativoTest).filter(TentativoTest.test_id == test_id, TentativoTest.iscrizione_id == iscr.id).count()
    corso = db.query(Corso).filter(Corso.id == t.corso_id).first()
    # In una sessione sempre aperta non c'e' «una nuova edizione» in cui rifare il corso: si puo' sempre riprovare
    ignora_limite = corso.azione_test_non_superato.value == "rifai_test" or (edizione.sempre_aperta and corso.azione_test_non_superato.value == "rifai_corso")
    if t.tentativi_max and not ignora_limite and n_precedenti >= t.tentativi_max:
        raise HTTPException(400, "Numero massimo di tentativi raggiunto")

    n_corrette, n_domande = 0, len(t.domande)
    for d in t.domande:
        scelta = data.risposte.get(str(d.id))
        corretta = next((o for o in d.opzioni if o.corretta), None)
        if scelta and corretta and str(corretta.id) == scelta:
            n_corrette += 1
    punteggio = round((n_corrette / n_domande) * 100, 1) if n_domande else 0.0
    superato = punteggio >= t.soglia_superamento_pct

    tentativo = TentativoTest(test_id=test_id, iscrizione_id=iscr.id, risposte=data.risposte,
                               punteggio_pct=punteggio, superato=superato)
    db.add(tentativo)

    esito_extra = {}
    if t.momento == MomentoTest.finale:
        if edizione.sempre_aperta and not superato and corso.azione_test_non_superato.value == "rifai_corso":
            esito_extra = {"messaggio": "Test non superato: puoi ritentare."}
        else:
            esito_extra = _applica_policy_test(db, iscr, corso, superato)
        db.flush()
        cert_auto = completa_se_dovuto(db, request, iscr)      # sessione sempre aperta: se il video e' gia' visto, si completa ora
        if cert_auto:
            esito_extra["certificato_id"] = str(cert_auto.id)
            esito_extra["messaggio"] = "Corso completato: il tuo attestato è pronto."
        # Se l'edizione era già chiusa e l'unica cosa che mancava era superare il
        # test (policy rifai_test), il superamento ora completa retroattivamente.
        if superato and edizione.stato == StatoEdizione.chiusa and iscr.stato == StatoIscrizione.iscritto:
            iscr.stato = StatoIscrizione.completato
            iscr.completato_at = datetime.now(timezone.utc)
            iscr.versione_corso = corso.versione
            u = db.query(User).filter(User.id == iscr.user_id).first()
            azienda_nome, logo_path = cert_svc.azienda_info(db)
            cert = cert_svc.crea_certificato(db, iscr, corso, u.full_name if u else "", azienda_nome, logo_path, edizione)
            esito_extra["certificato_id"] = str(cert.id)
            esito_extra["messaggio"] = "Test superato: corso completato."

    audit_svc.log_from_request(db, request, user, "TEST_TENTATIVO", entity_type="test", entity_id=test_id,
                                entity_name=f"{corso.titolo} - {t.momento.value}" if corso else None,
                                detail=f"tentativo {n_precedenti + 1} - punteggio {punteggio}% - {'superato' if superato else 'non superato'}")
    db.commit()
    if esito_extra.get("certificato_id"):
        avanza_e_invita(db, user_ids=[user.id])                  # corso completato: i successivi del percorso si sbloccano
    return {"punteggio_pct": punteggio, "superato": superato, **esito_extra}

def _applica_policy_test(db: Session, iscrizione: Iscrizione, corso: Corso, superato: bool) -> dict:
    """Applica la policy del Corso quando un test finale è stato tentato.
    Ritorna info aggiuntive per il frontend (es. entro quando va ripetuto)."""
    from datetime import datetime, timedelta, timezone
    from ..models.iscrizione import StatoIscrizione
    if superato:
        return {}
    azione = corso.azione_test_non_superato.value
    if azione == "rifai_test":
        return {"messaggio": "Test non superato: puoi ritentare."}
    if azione == "rifai_corso":
        iscrizione.stato = StatoIscrizione.non_completato
        return {"messaggio": "Test non superato: il corso va rifatto da capo in un'altra sessione."}
    if azione == "concludi_scadenza_breve" and corso.giorni_scadenza_breve:
        iscrizione.ripeti_entro = datetime.now(timezone.utc) + timedelta(days=corso.giorni_scadenza_breve)
        return {"messaggio": f"Test non superato: dovrai ripetere il corso entro {corso.giorni_scadenza_breve} giorni."}
    # concludi_comunque: nessuna azione, il completamento segue le evidenze normali
    return {"messaggio": "Test non superato, ma il corso risulta comunque concluso."}

@router.get("/api/test/{test_id}/report.csv")
def report_test_csv(test_id: str, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    t = db.query(Test).filter(Test.id == test_id).first()
    if not t: raise HTTPException(404)
    rows = db.query(TentativoTest).filter(TentativoTest.test_id == test_id).order_by(TentativoTest.completato_at.desc()).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Utente", "Email", "Punteggio %", "Superato", "Data"])
    for r in rows:
        iscr = db.query(Iscrizione).filter(Iscrizione.id == r.iscrizione_id).first()
        u = db.query(User).filter(User.id == iscr.user_id).first() if iscr else None
        w.writerow([neutralizza(u.full_name) if u else "", u.email if u else "", r.punteggio_pct,
                    "Sì" if r.superato else "No", r.completato_at.strftime("%d/%m/%Y %H:%M") if r.completato_at else ""])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                              headers={"Content-Disposition": f"attachment; filename=report_test_{test_id}.csv"})
