import time
import traceback
from datetime import datetime, timezone
from ..database import SessionLocal
from ..models.job_run import JobRun

def esegui_tracciato(job_id: str, fn):
    """Esegue fn(db) registrando l'esito in job_runs. L'eccezione viene
    registrata e NON rilanciata: un job fallito non deve fermare lo scheduler."""
    started = datetime.now(timezone.utc)
    t0 = time.monotonic()
    esito, errore, dettaglio = "ok", None, None
    db = SessionLocal()
    try:
        risultato = fn(db)
        dettaglio = risultato if isinstance(risultato, str) else None
    except Exception:
        db.rollback()
        esito, errore = "errore", traceback.format_exc()[-4000:]
        print(f"[scheduler] job {job_id} fallito:\n{errore}")
    finally:
        db.close()
    db = SessionLocal()
    try:
        db.add(JobRun(job_id=job_id, started_at=started, finished_at=datetime.now(timezone.utc),
                      esito=esito, durata_ms=int((time.monotonic() - t0) * 1000), errore=errore, dettaglio=dettaglio))
        db.commit()
    finally:
        db.close()
