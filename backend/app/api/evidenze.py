import os, re, uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
from ..database import get_db
from ..models.edizione import Edizione, StatoEdizione, ModalitaTeams
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.evidenza import Evidenza, FonteEvidenza
from ..models.certificato import Certificato
from ..models.user import User
from ..models.corso import Corso
from ..services import certificati as cert_svc
from ..services.durata import congela as congela_durata
from ..services import audit as audit_svc
from ..services import graph as graph_svc
from ..services import cifratura
from .deps import get_current_user, require_training_admin
from .edizioni import _is_docente
from ..services.impronte import impronta

MAX_ALLEGATO_BYTES = 25 * 1024 * 1024   # attestati esterni: PDF o immagini

router = APIRouter(prefix="/api/edizioni/{edizione_id}", tags=["evidenze"])

def _get_edizione(db, edizione_id):
    e = db.query(Edizione).filter(Edizione.id == edizione_id).first()
    if not e: raise HTTPException(404, "Edizione non trovata")
    return e

def _get_iscrizione(db, edizione_id, user_id):
    i = db.query(Iscrizione).filter(Iscrizione.edizione_id == edizione_id, Iscrizione.user_id == user_id).first()
    if not i: raise HTTPException(400, "Utente non iscritto a questa edizione")
    return i

# --- Checkin discente (self, in attesa di validazione docente) ---

class CheckinDiscenteIn(BaseModel):
    momento: str  # "inizio" | "fine"

@router.post("/checkin/discente")
def checkin_discente(edizione_id: str, data: CheckinDiscenteIn, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    e = _get_edizione(db, edizione_id)
    if e.stato == StatoEdizione.chiusa: raise HTTPException(400, "Edizione già chiusa")
    i = _get_iscrizione(db, edizione_id, user.id)
    ev = db.query(Evidenza).filter(Evidenza.iscrizione_id == i.id, Evidenza.fonte == FonteEvidenza.checkin_discente).first()
    if not ev:
        ev = Evidenza(iscrizione_id=i.id, fonte=FonteEvidenza.checkin_discente)
        db.add(ev)
    now = datetime.now(timezone.utc)
    if data.momento == "inizio": ev.inizio_at = now
    elif data.momento == "fine": ev.fine_at = now
    else: raise HTTPException(400, "momento deve essere 'inizio' o 'fine'")
    audit_svc.log_from_request(db, request, user, "CHECKIN_INIZIO" if data.momento == "inizio" else "CHECKIN_FINE",
                                entity_type="edizione", entity_id=edizione_id, entity_name=audit_svc.nome_edizione(db, e))
    db.commit()
    return {"ok": True, "inizio_at": ev.inizio_at, "fine_at": ev.fine_at}

# --- Checkin docente (registro digitale compilato dal docente) ---

class PresenzaRiga(BaseModel):
    user_id: str
    presente: bool
    inizio_at: Optional[datetime] = None
    fine_at: Optional[datetime] = None

@router.post("/checkin/docente")
def checkin_docente(edizione_id: str, righe: List[PresenzaRiga], request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    e = _get_edizione(db, edizione_id)
    if not (_is_docente(e, user) or user.ha_poteri_formazione):
        raise HTTPException(403, "Solo il docente dell'edizione può compilare il registro")
    if e.stato == StatoEdizione.chiusa: raise HTTPException(400, "Edizione già chiusa")
    now = datetime.now(timezone.utc)
    registrati = []
    for r in righe:
        if not r.presente: continue
        registrati.append(audit_svc.nome_utente(db, r.user_id))
        i = _get_iscrizione(db, edizione_id, r.user_id)
        ev = db.query(Evidenza).filter(Evidenza.iscrizione_id == i.id, Evidenza.fonte == FonteEvidenza.checkin_docente).first()
        if not ev:
            ev = Evidenza(iscrizione_id=i.id, fonte=FonteEvidenza.checkin_docente)
            db.add(ev)
        ev.inizio_at = r.inizio_at or ev.inizio_at or now
        ev.fine_at = r.fine_at or now
    audit_svc.log_from_request(db, request, user, "REGISTRO_PRESENZE", entity_type="edizione", entity_id=edizione_id,
                                entity_name=audit_svc.nome_edizione(db, e),
                                detail=f"presenti registrati: {len(registrati)}" + (f" ({', '.join(registrati[:10])}{'...' if len(registrati) > 10 else ''})" if registrati else ""))
    db.commit()
    return {"ok": True}

# --- Teams ---

class TeamsLinkIn(BaseModel):
    join_url: str

@router.post("/teams/link")
def teams_link_manuale(edizione_id: str, data: TeamsLinkIn, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    e = _get_edizione(db, edizione_id)
    e.teams_join_url = data.join_url
    e.teams_mode = ModalitaTeams.manuale
    audit_svc.log_from_request(db, request, user, "TEAMS_LINK", entity_type="edizione", entity_id=edizione_id,
                                entity_name=audit_svc.nome_edizione(db, e), detail="link riunione impostato a mano")
    db.commit()
    return {"ok": True}

@router.post("/teams/crea-riunione")
async def teams_crea_riunione(edizione_id: str, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    e = _get_edizione(db, edizione_id)
    docente = next((d for d in e.docenti), None)
    organizer = db.query(User).filter(User.id == docente.user_id).first() if docente else None
    if not organizer:
        raise HTTPException(400, "Assegna prima un docente all'edizione")
    corso = db.query(Corso).filter(Corso.id == e.corso_id).first()
    risultato = await graph_svc.crea_riunione(
        organizer.email, corso.titolo if corso else "Formazione",
        e.data_inizio.isoformat() if e.data_inizio else datetime.now(timezone.utc).isoformat(),
        e.data_fine.isoformat() if e.data_fine else datetime.now(timezone.utc).isoformat(),
    )
    if not risultato:
        raise HTTPException(400, "Creazione automatica non disponibile (Graph non configurato/consenso admin mancante) — usa 'incolla link riunione'")
    e.teams_meeting_id = risultato["id"]
    e.teams_join_url = risultato["joinUrl"]
    e.teams_mode = ModalitaTeams.auto
    audit_svc.log_from_request(db, request, user, "TEAMS_CREA_RIUNIONE", entity_type="edizione", entity_id=edizione_id,
                                entity_name=audit_svc.nome_edizione(db, e))
    db.commit()
    return {"ok": True, "join_url": e.teams_join_url}

@router.post("/teams/sincronizza-presenze")
async def teams_sincronizza(edizione_id: str, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    e = _get_edizione(db, edizione_id)
    if not e.teams_meeting_id:
        raise HTTPException(400, "Nessuna riunione Teams associata (crea automaticamente o incolla il link)")
    docente = next((d for d in e.docenti), None)
    organizer = db.query(User).filter(User.id == docente.user_id).first() if docente else None
    records = await graph_svc.scarica_report_presenze(organizer.email, e.teams_meeting_id) if organizer else None
    if records is None:
        raise HTTPException(400, "Report non disponibile via Graph — usa 'report manuale'")
    esito = _applica_records_teams(db, e, records, FonteEvidenza.teams_auto)
    audit_svc.log_from_request(db, request, user, "TEAMS_SINCRONIZZA_PRESENZE", entity_type="edizione", entity_id=edizione_id,
                                entity_name=audit_svc.nome_edizione(db, e), detail=f"presenze applicate: {len(esito['applicati'])}")
    db.commit()
    return esito

class ReportManualeRiga(BaseModel):
    email: str
    durata_minuti: Optional[int] = None
    inizio_at: Optional[datetime] = None
    fine_at: Optional[datetime] = None

@router.post("/teams/report-manuale")
def teams_report_manuale(edizione_id: str, righe: List[ReportManualeRiga], request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    e = _get_edizione(db, edizione_id)
    records = [{"emailAddress": r.email, "durata_minuti": r.durata_minuti,
                "joinDateTime": r.inizio_at.isoformat() if r.inizio_at else None,
                "leaveDateTime": r.fine_at.isoformat() if r.fine_at else None} for r in righe]
    esito = _applica_records_teams(db, e, records, FonteEvidenza.teams_manuale)
    audit_svc.log_from_request(db, request, user, "TEAMS_REPORT_MANUALE", entity_type="edizione", entity_id=edizione_id,
                                entity_name=audit_svc.nome_edizione(db, e), detail=f"presenze applicate: {len(esito['applicati'])}")
    db.commit()
    return esito

def _applica_records_teams(db: Session, e: Edizione, records: list, fonte: FonteEvidenza):
    applicati = []
    for rec in records:
        email = (rec.get("emailAddress") or rec.get("identity", {}).get("user", {}).get("id") or "").lower()
        u = db.query(User).filter(User.email_idx == impronta(email)).first()
        if not u: continue
        i = db.query(Iscrizione).filter(Iscrizione.edizione_id == e.id, Iscrizione.user_id == u.id).first()
        if not i: continue
        ev = db.query(Evidenza).filter(Evidenza.iscrizione_id == i.id, Evidenza.fonte == fonte).first()
        if not ev:
            ev = Evidenza(iscrizione_id=i.id, fonte=fonte)
            db.add(ev)
        if rec.get("joinDateTime"): ev.inizio_at = datetime.fromisoformat(rec["joinDateTime"].replace("Z", "+00:00"))
        if rec.get("leaveDateTime"): ev.fine_at = datetime.fromisoformat(rec["leaveDateTime"].replace("Z", "+00:00"))
        ev.dati_extra = {**(ev.dati_extra or {}), "durata_minuti": rec.get("durata_minuti")}
        applicati.append(email)
    db.commit()
    return {"ok": True, "applicati": applicati}

# --- Evidenza esterna: attestato caricato manualmente ---

@router.post("/evidenze/{iscrizione_id}/upload")
async def upload_evidenza_esterna(edizione_id: str, iscrizione_id: str, request: Request,
                                   ore: Optional[int] = Form(None),
                                   data_evento: Optional[str] = Form(None),
                                   file: UploadFile = File(...),
                                   db: Session = Depends(get_db), user=Depends(require_training_admin)):
    i = db.query(Iscrizione).filter(Iscrizione.id == iscrizione_id, Iscrizione.edizione_id == edizione_id).first()
    if not i: raise HTTPException(404)
    upload_dir = "/app/uploads/attestati_esterni"
    os.makedirs(upload_dir, exist_ok=True)
    nome_sicuro = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename((file.filename or "allegato").replace("\\", "/")))[-80:] or "allegato"
    path = os.path.join(upload_dir, f"{iscrizione_id}_{uuid.uuid4().hex[:8]}_{nome_sicuro}")
    await cifratura.salva_upload(file, path, MAX_ALLEGATO_BYTES, lambda lim: HTTPException(413, f"File troppo grande (massimo {lim // (1024 * 1024)} MB)"))
    ev = Evidenza(iscrizione_id=i.id, fonte=FonteEvidenza.upload_manuale,
                  file_allegato_path=path, dati_extra={"ore": ore, "data_evento": data_evento})
    db.add(ev)
    e_up = db.query(Edizione).filter(Edizione.id == edizione_id).first()
    audit_svc.log_from_request(db, request, user, "UPLOAD_EVIDENZA", entity_type="edizione", entity_id=edizione_id,
                                entity_name=audit_svc.nome_edizione(db, e_up) if e_up else None,
                                detail=f"attestato esterno per {audit_svc.nome_utente(db, i.user_id)} - file: {file.filename}")
    db.commit()
    return {"ok": True}

# --- Chiusura edizione: attesta le evidenze, calcola completamento, genera certificati ---

SOGLIA_COMPLETAMENTO_VIDEO_PCT = 80  # un video visto per questa percentuale vale come completato (usata anche per l'audit in api/video.py)

def _evidenza_indica_completamento(ev: Evidenza) -> bool:
    if ev is None: return False
    if ev.percentuale_completamento is not None:
        return ev.percentuale_completamento >= SOGLIA_COMPLETAMENTO_VIDEO_PCT      # un video visto per poco non vale come completato
    return ev.inizio_at is not None and ev.fine_at is not None

def _test_permette_completamento(db: Session, iscrizione: Iscrizione, corso: Corso):
    """Ritorna (ok, in_attesa_ritentativo). ok=False + in_attesa=True significa
    che l'iscrizione resta 'iscritto' (policy rifai_test) invece di essere
    marcata come non completata."""
    from ..models.test import Test, TentativoTest, MomentoTest
    from .test import _applica_policy_test
    test_finale = db.query(Test).filter(Test.corso_id == corso.id, Test.momento == MomentoTest.finale).first()
    if not test_finale:
        return True, False
    ultimo = db.query(TentativoTest).filter(
        TentativoTest.test_id == test_finale.id, TentativoTest.iscrizione_id == iscrizione.id
    ).order_by(TentativoTest.completato_at.desc()).first()
    if ultimo and ultimo.superato:
        return True, False
    _applica_policy_test(db, iscrizione, corso, superato=False)
    azione = corso.azione_test_non_superato.value
    if azione == "rifai_test":
        return False, True
    if azione == "rifai_corso":
        return False, False  # iscrizione.stato già impostato a non_completato
    return True, False  # concludi_comunque / concludi_scadenza_breve

@router.post("/chiudi")
def chiudi_edizione(edizione_id: str, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    e = _get_edizione(db, edizione_id)
    if not (_is_docente(e, user) or user.ha_poteri_formazione):
        raise HTTPException(403, "Solo un docente dell'edizione o l'ufficio formazione può chiudere l'edizione")
    if e.stato == StatoEdizione.chiusa:
        raise HTTPException(400, "Già chiusa")

    now = datetime.now(timezone.utc)
    iscrizioni = db.query(Iscrizione).filter(Iscrizione.edizione_id == edizione_id).all()
    corso = db.query(Corso).filter(Corso.id == e.corso_id).first()
    congela_durata(e, corso)   # la durata di oggi resta quella della sessione: gli attestati che emettiamo ora non cambiano piu'
    esito = []
    for i in iscrizioni:
        evidenze = db.query(Evidenza).filter(Evidenza.iscrizione_id == i.id).all()
        for ev in evidenze:
            if not ev.attestata_da_id:
                ev.attestata_da_id = user.id
                ev.attestata_at = now

        if i.stato in (StatoIscrizione.annullato, StatoIscrizione.in_lista_attesa):
            continue        # non hanno partecipato: la chiusura non le tocca (prima diventavano «non completato»)
        if i.stato == StatoIscrizione.completato:
            # gia' completata (un video lo fa da solo): niente secondo attestato
            gia = db.query(Certificato).filter(Certificato.iscrizione_id == i.id).order_by(Certificato.emesso_at.desc()).first()
            esito.append({"user_id": str(i.user_id), "completato": True, "certificato_id": str(gia.id) if gia else None})
            continue
        if i.stato == StatoIscrizione.non_completato:
            # già deciso da un tentativo test con policy rifai_corso prima della chiusura
            esito.append({"user_id": str(i.user_id), "completato": False})
            continue

        evidenza_ok = any(_evidenza_indica_completamento(ev) for ev in evidenze)
        test_ok, in_attesa_ritentativo = _test_permette_completamento(db, i, corso)
        completato = evidenza_ok and test_ok

        if completato:
            i.stato = StatoIscrizione.completato
            i.completato_at = now
            i.versione_corso = corso.versione if corso else None
            u = db.query(User).filter(User.id == i.user_id).first()
            azienda_nome, logo_path = cert_svc.azienda_info(db)
            cert = cert_svc.crea_certificato(db, i, corso, u.full_name if u else "", azienda_nome, logo_path, e)
            esito.append({"user_id": str(i.user_id), "completato": True, "certificato_id": str(cert.id)})
        elif in_attesa_ritentativo:
            esito.append({"user_id": str(i.user_id), "completato": False, "in_attesa_ritentativo_test": True})
        else:
            i.stato = StatoIscrizione.non_completato
            esito.append({"user_id": str(i.user_id), "completato": False})

    e.stato = StatoEdizione.chiusa
    e.chiusa_da_id = user.id
    e.chiusa_at = now
    audit_svc.log_from_request(db, request, user, "CLOSE", entity_type="edizione", entity_id=str(e.id),
                                entity_name=audit_svc.nome_edizione(db, e),
                                detail=f"completati: {sum(1 for x in esito if x.get('completato'))}/{len(esito)}")
    db.commit()
    return {"ok": True, "esiti": esito}

# --- Report CSV ---

@router.get("/report/iscrizioni.csv")
def report_iscrizioni_csv(edizione_id: str, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    import csv, io
    from fastapi.responses import StreamingResponse
    e = _get_edizione(db, edizione_id)
    corso = db.query(Corso).filter(Corso.id == e.corso_id).first()
    iscrizioni = db.query(Iscrizione).filter(Iscrizione.edizione_id == edizione_id).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Corso", "Utente", "Email", "Stato", "Ripeti entro"])
    for i in iscrizioni:
        u = db.query(User).filter(User.id == i.user_id).first()
        w.writerow([corso.titolo if corso else "", u.full_name if u else "", u.email if u else "",
                    i.stato, i.ripeti_entro.strftime("%d/%m/%Y") if i.ripeti_entro else ""])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                              headers={"Content-Disposition": f"attachment; filename=iscrizioni_{edizione_id}.csv"})
