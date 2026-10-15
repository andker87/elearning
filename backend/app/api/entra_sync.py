from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models.job_run import JobRun
from ..services import audit as audit_svc
from ..services import entra_sync as svc
from .deps import require_admin_tecnico

router = APIRouter(prefix="/api/admin/entra", tags=["entra-sync"])


def _richiedi_configurato():
    if not settings.entra_sync_enabled:
        raise HTTPException(400, "Sincronizzazione non configurata: servono le credenziali Graph e ENTRA_SYNC_GRUPPO_ID nell'ambiente")


def _piano(db: Session):
    try:
        return svc.calcola_piano(db, svc.leggi_membri())
    except svc.EntraErrore as e:
        raise HTTPException(502, f"Entra ID non raggiungibile: {e}")
    except Exception as e:  # rete, JSON inatteso...
        raise HTTPException(502, f"Entra ID non raggiungibile: {str(e)[:150]}")


@router.get("/stato")
def stato(db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    ultime = db.query(JobRun).filter(JobRun.job_id == "sync_entra").order_by(JobRun.started_at.desc()).limit(5).all()
    return {
        "configurato": settings.entra_sync_enabled, "graph": settings.graph_enabled, "automatico": bool(settings.ENTRA_SYNC_AUTO),
        "ultime": [{"started_at": r.started_at, "esito": r.esito, "dettaglio": r.dettaglio, "errore": r.errore} for r in ultime],
    }


@router.post("/anteprima")
def anteprima(db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    _richiedi_configurato()
    return _piano(db)


@router.post("/applica")
def applica(request: Request, riattiva: bool = False, forza: bool = False, db: Session = Depends(get_db), user=Depends(require_admin_tecnico)):
    _richiedi_configurato()
    piano = _piano(db)
    if piano["freno"] and not forza:
        raise HTTPException(409, f"Piano sospetto, non applicato: {piano['freno']}. Se è corretto, conferma di forzare.")
    esito = svc.applica_piano(db, piano, request=request, admin=user, riattiva=riattiva)
    audit_svc.log_from_request(db, request, user, "SYNC_ENTRA", entity_type="user", entity_name="Sincronizzazione Entra", detail=svc.riepilogo(esito))
    db.commit()
    return esito
