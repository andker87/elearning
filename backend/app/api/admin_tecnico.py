import os
import shutil
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text, func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..config import settings
from ..services.export import esporta
from ..models.audit import AuditLog
from ..models.job_run import JobRun
from ..models.user import User
from ..models.video import VideoContenuto, StatoVideo
from .deps import require_admin_tecnico

router = APIRouter(prefix="/api/admin", tags=["admin-tecnico"])

JOB_NOTIFICHE = "notifiche_giornaliere"
LIMITE_ESPORTAZIONE_CSV = 50000
LIMITE_ESPORTAZIONE_PDF = 2000
CARTELLE_STORAGE = {"video": "/app/videos", "upload": "/app/uploads"}


def _dimensione_cartella(path: str) -> int:
    totale = 0
    for radice, _, files in os.walk(path):
        for nome in files:
            try:
                totale += os.path.getsize(os.path.join(radice, nome))
            except OSError:
                pass
    return totale


def _stato_entra(db: Session) -> dict:
    ultima = db.query(JobRun).filter(JobRun.job_id == "sync_entra").order_by(JobRun.started_at.desc()).first()
    return {"configurato": bool(settings.entra_sync_enabled), "automatico": bool(settings.ENTRA_SYNC_AUTO),
            "ultima_esecuzione": {"started_at": ultima.started_at, "esito": ultima.esito, "dettaglio": ultima.dettaglio,
                                   "errore": ultima.errore} if ultima else None}


@router.get("/salute")
def salute(db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    now = datetime.now(timezone.utc)

    def login_distinti(ore: int) -> int:
        return db.query(func.count(func.distinct(AuditLog.user_id))).filter(
            AuditLog.action == "LOGIN", AuditLog.created_at >= now - timedelta(hours=ore)).scalar() or 0

    login_falliti_24h = db.query(func.count(AuditLog.id)).filter(
        AuditLog.action == "LOGIN_FAILED", AuditLog.created_at >= now - timedelta(hours=24)).scalar() or 0

    from ..main import scheduler
    job = scheduler.get_job(JOB_NOTIFICHE)
    ultime = db.query(JobRun).filter(JobRun.job_id == JOB_NOTIFICHE).order_by(JobRun.started_at.desc()).limit(10).all()
    ultima = ultime[0] if ultime else None

    try:
        disco = shutil.disk_usage("/app/videos")
    except OSError:  # cartella non montata: la salute del resto va mostrata lo stesso
        disco = None
    video_per_stato = dict(db.query(VideoContenuto.stato, func.count(VideoContenuto.id)).group_by(VideoContenuto.stato).all())

    return {
        "generato_at": now,
        "accessi": {
            "utenti_distinti_24h": login_distinti(24),
            "utenti_distinti_7g": login_distinti(24 * 7),
            "login_falliti_24h": login_falliti_24h,
        },
        "scheduler": {
            "attivo": scheduler.running,
            "prossima_esecuzione": job.next_run_time if job else None,
            "ultima_esecuzione": {
                "started_at": ultima.started_at, "esito": ultima.esito,
                "durata_ms": ultima.durata_ms, "errore": ultima.errore,
            } if ultima else None,
            "storico": [{"started_at": r.started_at, "esito": r.esito, "durata_ms": r.durata_ms, "errore": r.errore}
                        for r in ultime],
        },
        "smtp": {"configurato": bool(settings.smtp_enabled)},
        "entra": _stato_entra(db),
        "sso": {"configurato": bool(settings.sso_enabled), "provisioning": bool(settings.SSO_PROVISIONA_UTENTI),
                "utenti_collegati": db.query(func.count(User.id)).filter(User.sso_subject.isnot(None)).scalar() or 0},
        "storage": {
            "disco_totale": disco.total if disco else None, "disco_usato": disco.used if disco else None,
            "disco_libero": disco.free if disco else None,
            "video_bytes": _dimensione_cartella(CARTELLE_STORAGE["video"]),
            "upload_bytes": _dimensione_cartella(CARTELLE_STORAGE["upload"]),
            "video_per_stato": {(k.value if hasattr(k, "value") else str(k)): v for k, v in video_per_stato.items()},
            "video_in_errore": video_per_stato.get(StatoVideo.errore, 0),
        },
        "database": {
            "dimensione_bytes": db.execute(text("SELECT pg_database_size(current_database())")).scalar(),
            "righe_audit": db.query(func.count(AuditLog.id)).scalar(),
        },
    }


def _filtra_audit(db: Session, q, action, entity_type, utente, ip, da, a):
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if utente:
        query = query.filter(AuditLog.user_email.ilike(f"%{utente}%"))
    if ip:
        query = query.filter(AuditLog.ip_address.ilike(f"%{ip}%"))
    if da:
        query = query.filter(AuditLog.created_at >= da)
    if a:
        # "a" e' una data (mezzanotte): vale tutto quel giorno; con un orario preciso vale fino a quell'istante
        fine_giorno = a.hour == a.minute == a.second == a.microsecond == 0
        query = query.filter(AuditLog.created_at < a + timedelta(days=1)) if fine_giorno else query.filter(AuditLog.created_at <= a)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(AuditLog.entity_name.ilike(like), AuditLog.detail.ilike(like),
                                  AuditLog.entity_id.ilike(like), AuditLog.user_email.ilike(like)))
    return query


def _serialize_audit(r: AuditLog):
    return {
        "id": str(r.id), "created_at": r.created_at,
        "user_id": str(r.user_id) if r.user_id else None, "user_email": r.user_email,
        "action": r.action, "entity_type": r.entity_type, "entity_id": r.entity_id,
        "entity_name": r.entity_name, "detail": r.detail, "ip_address": r.ip_address,
    }


@router.get("/audit")
def lista_audit(
    q: Optional[str] = None, action: Optional[str] = None, entity_type: Optional[str] = None,
    utente: Optional[str] = None, ip: Optional[str] = None,
    da: Optional[datetime] = None, a: Optional[datetime] = None,
    pagina: int = Query(1, ge=1), per_pagina: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db), user=Depends(require_admin_tecnico),
):
    query = _filtra_audit(db, q, action, entity_type, utente, ip, da, a)
    totale = query.count()
    righe = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset((pagina - 1) * per_pagina).limit(per_pagina).all()
    return {"totale": totale, "pagina": pagina, "per_pagina": per_pagina, "items": [_serialize_audit(r) for r in righe]}


@router.get("/audit/filtri")
def filtri_audit(db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    return {
        "azioni": [r[0] for r in db.query(AuditLog.action).distinct().order_by(AuditLog.action).all() if r[0]],
        "entita": [r[0] for r in db.query(AuditLog.entity_type).distinct().order_by(AuditLog.entity_type).all() if r[0]],
    }


@router.get("/audit/export")
def esporta_audit(
    formato: str = "csv", pagina: str = "A4",
    q: Optional[str] = None, action: Optional[str] = None, entity_type: Optional[str] = None,
    utente: Optional[str] = None, ip: Optional[str] = None,
    da: Optional[datetime] = None, a: Optional[datetime] = None,
    db: Session = Depends(get_db), user=Depends(require_admin_tecnico),
):
    """Stessi filtri dell'elenco, senza paginazione. Il PDF e' limitato: migliaia
    di righe in una tabella A4/A3 non sono leggibili, per quelle serve Excel."""
    limite = LIMITE_ESPORTAZIONE_PDF if formato == "pdf" else LIMITE_ESPORTAZIONE_CSV
    query = _filtra_audit(db, q, action, entity_type, utente, ip, da, a)
    totale = query.count()
    righe = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limite).all()
    colonne = ["Data", "Utente", "Azione", "Tipo entità", "ID entità", "Nome entità", "Dettaglio", "IP"]
    dati = [[r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "", r.user_email or "", r.action,
             r.entity_type or "", r.entity_id or "", r.entity_name or "", r.detail or "", r.ip_address or ""] for r in righe]
    if totale > limite:  # il taglio non deve passare inosservato: l'ultima riga del file lo dice
        dati.append(["", "", "ATTENZIONE", "", "", "", f"Esportate {limite} righe su {totale}: restringi i filtri o usa Excel", ""])
    return esporta(formato, "audit_log", "Audit log", colonne, dati, pagina)
