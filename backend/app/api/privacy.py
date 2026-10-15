import json
import os
import uuid as uuidlib
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.audit import AuditLog
from ..models.autoiscrizione import AutoIscrizioneRichiesta
from ..models.certificato import Certificato
from ..models.evidenza import Evidenza
from ..models.azienda import Azienda
from ..models.group import Group, UserGroup
from ..models.iscrizione import Iscrizione
from ..models.notification import Notification
from ..models.percorso import PercorsoAssegnazione
from ..models.push_subscription import PushSubscription
from ..models.richiesta_corso import RichiestaCorso
from ..models.test import TentativoTest
from ..models.user import User
from ..models.video import VideoProgresso
from ..services import audit as audit_svc
from .deps import get_current_user, require_admin_tecnico

router = APIRouter(prefix="/api/privacy", tags=["privacy"])

# Colonne mai esportate: credenziali, token e chiavi del dispositivo.
INFORMATIVA_DIR = "/app/uploads/azienda"
INFORMATIVA_PDF = os.path.join(INFORMATIVA_DIR, "informativa-privacy.pdf")
INFORMATIVA_MAX_BYTES = 15 * 1024 * 1024

ESCLUSE = {"hashed_password", "calendar_token", "sso_subject", "p256dh", "auth", "endpoint"}


def _valore(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, uuidlib.UUID):
        return str(v)
    if isinstance(v, Enum):
        return v.value
    return v


def _riga(obj) -> dict:
    return {c.name: _valore(getattr(obj, c.name)) for c in obj.__table__.columns if c.name not in ESCLUSE}


@router.get("/export")
def esporta_miei_dati(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Tutti i dati personali dell'utente corrente (GDPR, accesso e portabilita').
    Il gradimento non e' incluso: e' anonimo per scelta e non va ricondotto alla persona."""
    isc = db.query(Iscrizione).filter(Iscrizione.user_id == user.id).all()
    isc_ids = [i.id for i in isc]
    gruppi = [g.name for g in db.query(Group).join(UserGroup, UserGroup.group_id == Group.id).filter(UserGroup.user_id == user.id)]

    def per_iscrizioni(modello):
        return [_riga(r) for r in db.query(modello).filter(modello.iscrizione_id.in_(isc_ids))] if isc_ids else []

    dati = {
        "generato_il": datetime.now(timezone.utc).isoformat(),
        "profilo": _riga(user),
        "gruppi": gruppi,
        "iscrizioni": [_riga(i) for i in isc],
        "evidenze": per_iscrizioni(Evidenza),
        "tentativi_test": per_iscrizioni(TentativoTest),
        "progressi_video": [_riga(r) for r in db.query(VideoProgresso).filter(VideoProgresso.iscrizione_id.in_([str(i) for i in isc_ids]))] if isc_ids else [],
        "certificati": per_iscrizioni(Certificato),
        "percorsi_assegnati": [_riga(r) for r in db.query(PercorsoAssegnazione).filter(PercorsoAssegnazione.user_id == user.id)],
        "richieste_corso": [_riga(r) for r in db.query(RichiestaCorso).filter(RichiestaCorso.richiedente_id == user.id)],
        "richieste_autoiscrizione": [_riga(r) for r in db.query(AutoIscrizioneRichiesta).filter(AutoIscrizioneRichiesta.user_id == user.id)],
        "notifiche": [_riga(r) for r in db.query(Notification).filter(Notification.user_id == user.id)],
        "dispositivi_notifiche_push": db.query(PushSubscription).filter(PushSubscription.user_id == user.id).count(),
        "attivita_registrata": [_riga(r) for r in db.query(AuditLog).filter(AuditLog.user_id == user.id).order_by(AuditLog.created_at.desc())],
    }
    audit_svc.log_from_request(db, request, user, "EXPORT_DATI_PERSONALI", entity_type="user", entity_id=str(user.id), entity_name=user.email)
    db.commit()
    return Response(content=json.dumps(dati, ensure_ascii=False, indent=2, default=str), media_type="application/json",
                     headers={"Content-Disposition": 'attachment; filename="i-miei-dati.json"'})


# --- Informativa privacy -------------------------------------------------
# Un solo documento, consultabile da ogni utente dal proprio profilo. Nessuna
# accettazione al login: la piattaforma e' uno strumento aziendale, il
# trattamento non si basa sul consenso. Puo' essere testo, PDF o entrambi.

class InformativaIn(BaseModel):
    testo: Optional[str] = None


def _azienda(db: Session) -> Azienda:
    a = db.query(Azienda).first()
    if not a:
        a = Azienda()
        db.add(a)
        db.flush()
    return a


def _informativa(a: Optional[Azienda]) -> dict:
    pdf = bool(a and a.privacy_pdf_path and os.path.exists(a.privacy_pdf_path))
    testo = (a.privacy_testo or "").strip() if a else ""
    return {
        "presente": bool(testo or pdf),
        "testo": testo or None,
        "pdf_url": "/uploads/azienda/informativa-privacy.pdf" if pdf else None,
        "aggiornata_at": a.privacy_aggiornata_at if a else None,
        "titolare": (a.ragione_sociale if a else None),
        "contatto": (a.pec or a.email) if a else None,
    }


@router.get("/informativa")
def leggi_informativa(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _informativa(db.query(Azienda).first())


@router.put("/informativa")
def salva_testo_informativa(data: InformativaIn, request: Request, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    a = _azienda(db)
    a.privacy_testo = (data.testo or "").strip() or None
    a.privacy_aggiornata_at = datetime.now(timezone.utc)
    audit_svc.log_from_request(db, request, user, "UPDATE", entity_type="azienda", entity_name="Informativa privacy",
                                detail="testo aggiornato" if a.privacy_testo else "testo rimosso")
    db.commit()
    return _informativa(a)


@router.post("/informativa/pdf")
def carica_pdf_informativa(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    # Il Content-Type dichiarato dal client e' falsificabile: conta la firma del file.
    contenuto = file.file.read(INFORMATIVA_MAX_BYTES + 1)
    if len(contenuto) > INFORMATIVA_MAX_BYTES:
        raise HTTPException(400, "Il PDF supera i 15 MB")
    if not contenuto.startswith(b"%PDF-"):
        raise HTTPException(400, "Il file caricato non e' un PDF valido")
    a = _azienda(db)
    os.makedirs(INFORMATIVA_DIR, exist_ok=True)
    with open(INFORMATIVA_PDF, "wb") as f:
        f.write(contenuto)
    a.privacy_pdf_path = INFORMATIVA_PDF
    a.privacy_aggiornata_at = datetime.now(timezone.utc)
    audit_svc.log_from_request(db, request, user, "UPDATE", entity_type="azienda", entity_name="Informativa privacy",
                                detail=f"PDF caricato ({file.filename or 'senza nome'}, {len(contenuto) // 1024} KB)")
    db.commit()
    return _informativa(a)


@router.delete("/informativa/pdf")
def elimina_pdf_informativa(request: Request, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    a = _azienda(db)
    if os.path.exists(INFORMATIVA_PDF):
        os.remove(INFORMATIVA_PDF)
    a.privacy_pdf_path = None
    a.privacy_aggiornata_at = datetime.now(timezone.utc)
    audit_svc.log_from_request(db, request, user, "DELETE", entity_type="azienda", entity_name="Informativa privacy", detail="PDF rimosso")
    db.commit()
    return _informativa(a)
