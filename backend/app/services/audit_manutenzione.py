"""Manutenzione del registro attivita': esportazione giornaliera dei log e pulizia di quelli vecchi.

- AUDIT_EXPORT_DIR: se impostata, ogni giorno trascorso viene scritto in <cartella>/audit-AAAA-MM-GG.ndjson
  (una riga JSON per evento, giorni in UTC). Un collettore (Filebeat, Promtail, Fluentd, uno script...) puo'
  prelevare quei file. I giorni gia' esportati non si riscrivono.
- AUDIT_RETENZIONE_MESI: gli eventi piu' vecchi si cancellano (0 = mai). Se l'esportazione e' attiva, si
  cancella solo cio' che e' gia' stato esportato: un'esportazione fallita non fa perdere eventi.
"""
import json
import os
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, func
from sqlalchemy.orm import Session

from ..config import settings
from ..models.audit import AuditLog

GIORNI_PER_MESE = 30.44


def evento_json(r: AuditLog) -> dict:
    return {
        "id": str(r.id), "data": r.created_at.astimezone(timezone.utc).isoformat() if r.created_at else None,
        "utente_id": str(r.user_id) if r.user_id else None, "utente": r.user_email, "azione": r.action,
        "entita_tipo": r.entity_type, "entita_id": r.entity_id, "entita_nome": r.entity_name,
        "dettaglio": r.detail, "ip": r.ip_address,
    }


def _file_giorno(giorno: date) -> str:
    return os.path.join(settings.AUDIT_EXPORT_DIR, f"audit-{giorno.isoformat()}.ndjson")


def _estremi_giorno(giorno: date):
    inizio = datetime.combine(giorno, time.min, tzinfo=timezone.utc)
    return inizio, inizio + timedelta(days=1)


def _esporta_giorno(db: Session, giorno: date) -> int:
    inizio, fine = _estremi_giorno(giorno)
    percorso = _file_giorno(giorno)
    provvisorio = f"{percorso}.parte"
    n = 0
    try:
        with open(provvisorio, "w", encoding="utf-8") as out:
            q = db.query(AuditLog).filter(AuditLog.created_at >= inizio, AuditLog.created_at < fine)
            for r in q.order_by(AuditLog.created_at, AuditLog.id).yield_per(1000):
                out.write(json.dumps(evento_json(r), ensure_ascii=False) + "\n")
                n += 1
        os.replace(provvisorio, percorso)
    except BaseException:
        if os.path.exists(provvisorio): os.remove(provvisorio)
        raise
    return n


def esporta_giorni_trascorsi(db: Session) -> int:
    """Scrive i file dei giorni passati ancora mancanti (dal primo evento a ieri). Ritorna i file scritti."""
    if not settings.AUDIT_EXPORT_DIR:
        return 0
    os.makedirs(settings.AUDIT_EXPORT_DIR, exist_ok=True)
    primo = db.query(func.min(AuditLog.created_at)).scalar()
    if primo is None:
        return 0
    oggi = datetime.now(timezone.utc).date()
    giorno, scritti = primo.astimezone(timezone.utc).date(), 0
    while giorno < oggi:
        if not os.path.exists(_file_giorno(giorno)):
            _esporta_giorno(db, giorno)
            scritti += 1
        giorno += timedelta(days=1)
    return scritti


def pulisci_vecchi(db: Session) -> int:
    """Cancella gli eventi oltre la conservazione. Con l'esportazione attiva, solo giorni gia' esportati."""
    mesi = settings.AUDIT_RETENZIONE_MESI
    if not mesi or mesi <= 0:
        return 0
    limite = (datetime.now(timezone.utc) - timedelta(days=int(mesi * GIORNI_PER_MESE))).date()   # giorni interi < limite
    primo = db.query(func.min(AuditLog.created_at)).scalar()
    if primo is None:
        return 0
    giorno, cancellati = primo.astimezone(timezone.utc).date(), 0
    while giorno < limite:
        if settings.AUDIT_EXPORT_DIR and not os.path.exists(_file_giorno(giorno)):
            break    # non ancora esportato: si aspetta
        inizio, fine = _estremi_giorno(giorno)
        cancellati += db.execute(delete(AuditLog).where(AuditLog.created_at >= inizio, AuditLog.created_at < fine)).rowcount
        db.commit()
        giorno += timedelta(days=1)
    return cancellati


def manutenzione(db: Session) -> str:
    """Job giornaliero. Il testo restituito finisce nello storico dei job."""
    scritti = esporta_giorni_trascorsi(db)
    cancellati = pulisci_vecchi(db)
    if cancellati:
        db.add(AuditLog(action="AUDIT_PULIZIA", entity_type="audit_log",
                        detail=f"cancellati {cancellati} eventi oltre {settings.AUDIT_RETENZIONE_MESI} mesi"))
        db.commit()
    return f"file esportati: {scritti}; eventi cancellati: {cancellati}"
