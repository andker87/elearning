import os, uuid, subprocess, json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import Optional
from ..database import get_db, SessionLocal
from ..models.video import VideoContenuto, VideoCapitolo, VideoProgresso, StatoVideo
from ..models.iscrizione import Iscrizione
from ..models.edizione import Edizione
from ..models.evidenza import Evidenza, FonteEvidenza
from .deps import get_current_user, require_training_admin

router = APIRouter(tags=["video"])

ORIGINALI_DIR = "/app/videos/originali"
PRONTI_DIR = "/app/videos/pronti"
SOTTOTITOLI_DIR = "/app/videos/sottotitoli"

def _serialize(v: VideoContenuto):
    return {
        "id": str(v.id), "titolo": v.titolo, "stato": v.stato,
        "durata_secondi": v.durata_secondi, "file_path": v.file_path,
        "sottotitoli_path": v.sottotitoli_path, "blocca_skip_avanti": v.blocca_skip_avanti,
        "capitoli": [{"id": str(c.id), "titolo": c.titolo, "inizio_secondi": c.inizio_secondi}
                     for c in sorted(v.capitoli, key=lambda x: x.inizio_secondi)],
    }

def _transcodifica(video_id: str, path_originale: str):
    """Gira in background dopo l'upload: normalizza in H.264/AAC con faststart
    per lo streaming progressivo, poi rileva la durata con ffprobe."""
    db = SessionLocal()
    try:
        v = db.query(VideoContenuto).filter(VideoContenuto.id == video_id).first()
        if not v: return
        v.stato = StatoVideo.in_elaborazione
        db.commit()
        out_path = os.path.join(PRONTI_DIR, f"{video_id}.mp4")
        try:
            subprocess.run([
                "ffmpeg", "-y", "-i", path_originale,
                "-c:v", "libx264", "-preset", "veloce" if False else "veryfast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out_path,
            ], check=True, capture_output=True, timeout=3600)
            probe = subprocess.run([
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "json", out_path,
            ], check=True, capture_output=True, text=True)
            durata = float(json.loads(probe.stdout)["format"]["duration"])
            v.file_path = out_path
            v.durata_secondi = int(durata)
            v.stato = StatoVideo.pronto
        except Exception as e:
            v.stato = StatoVideo.errore
        db.commit()
    finally:
        db.close()

@router.post("/api/video")
async def upload_video(background_tasks: BackgroundTasks, titolo: str = Form(...),
                        file: UploadFile = File(...), db: Session = Depends(get_db),
                        user=Depends(require_training_admin)):
    os.makedirs(ORIGINALI_DIR, exist_ok=True)
    video_id = uuid.uuid4()
    ext = os.path.splitext(file.filename or "")[1] or ".mp4"
    path_originale = os.path.join(ORIGINALI_DIR, f"{video_id}{ext}")
    with open(path_originale, "wb") as f:
        f.write(await file.read())
    v = VideoContenuto(id=video_id, titolo=titolo, file_originale=path_originale, stato=StatoVideo.caricato)
    db.add(v); db.commit()
    background_tasks.add_task(_transcodifica, str(video_id), path_originale)
    return _serialize(v)

@router.get("/api/video")
def list_video(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(VideoContenuto).options(joinedload(VideoContenuto.capitoli)).order_by(VideoContenuto.created_at.desc()).all()
    return [_serialize(v) for v in rows]

@router.get("/api/video/{video_id}")
def get_video(video_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = db.query(VideoContenuto).options(joinedload(VideoContenuto.capitoli)).filter(VideoContenuto.id == video_id).first()
    if not v: raise HTTPException(404)
    return _serialize(v)

class VideoUpdate(BaseModel):
    blocca_skip_avanti: Optional[bool] = None
    titolo: Optional[str] = None

@router.put("/api/video/{video_id}")
def update_video(video_id: str, data: VideoUpdate, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    v = db.query(VideoContenuto).filter(VideoContenuto.id == video_id).first()
    if not v: raise HTTPException(404)
    if data.blocca_skip_avanti is not None: v.blocca_skip_avanti = data.blocca_skip_avanti
    if data.titolo is not None: v.titolo = data.titolo
    db.commit()
    return {"ok": True}

class CapitoloIn(BaseModel):
    titolo: str
    inizio_secondi: int

@router.post("/api/video/{video_id}/capitoli")
def add_capitolo(video_id: str, data: CapitoloIn, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    if not db.query(VideoContenuto).filter(VideoContenuto.id == video_id).first():
        raise HTTPException(404)
    c = VideoCapitolo(video_id=video_id, titolo=data.titolo, inizio_secondi=data.inizio_secondi)
    db.add(c); db.commit()
    return {"ok": True, "id": str(c.id)}

@router.delete("/api/video/{video_id}/capitoli/{capitolo_id}")
def delete_capitolo(video_id: str, capitolo_id: str, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    db.query(VideoCapitolo).filter(VideoCapitolo.id == capitolo_id, VideoCapitolo.video_id == video_id).delete()
    db.commit()
    return {"ok": True}

@router.post("/api/video/{video_id}/sottotitoli")
async def upload_sottotitoli(video_id: str, file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(require_training_admin)):
    v = db.query(VideoContenuto).filter(VideoContenuto.id == video_id).first()
    if not v: raise HTTPException(404)
    os.makedirs(SOTTOTITOLI_DIR, exist_ok=True)
    path = os.path.join(SOTTOTITOLI_DIR, f"{video_id}.vtt")
    with open(path, "wb") as f:
        f.write(await file.read())
    v.sottotitoli_path = path
    db.commit()
    return {"ok": True}

# --- Tracciamento riproduzione (fonte di evidenza per il completamento) ---

class ProgressoIn(BaseModel):
    secondo_corrente: int

TOLLERANZA_SKIP_SECONDI = 15  # margine per buffering/heartbeat, non un vero "salta avanti"

@router.post("/api/iscrizioni/{iscrizione_id}/progresso")
def aggiorna_progresso(iscrizione_id: str, data: ProgressoIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    i = db.query(Iscrizione).filter(Iscrizione.id == iscrizione_id).first()
    if not i or str(i.user_id) != str(user.id):
        raise HTTPException(403, "Iscrizione non valida per l'utente corrente")
    e = db.query(Edizione).filter(Edizione.id == i.edizione_id).first()
    if not e or not e.video_id:
        raise HTTPException(400, "Questa edizione non ha un contenuto video associato")
    video = db.query(VideoContenuto).filter(VideoContenuto.id == e.video_id).first()

    prog = db.query(VideoProgresso).filter(VideoProgresso.iscrizione_id == iscrizione_id).first()
    if not prog:
        prog = VideoProgresso(iscrizione_id=iscrizione_id, secondo_massimo_raggiunto=0)
        db.add(prog); db.flush()

    if video.blocca_skip_avanti:
        tetto = prog.secondo_massimo_raggiunto + TOLLERANZA_SKIP_SECONDI
        nuovo = min(data.secondo_corrente, tetto)
    else:
        nuovo = data.secondo_corrente
    prog.secondo_massimo_raggiunto = max(prog.secondo_massimo_raggiunto, nuovo)

    percentuale = None
    if video.durata_secondi:
        percentuale = min(100.0, round(prog.secondo_massimo_raggiunto / video.durata_secondi * 100, 1))
        ev = db.query(Evidenza).filter(Evidenza.iscrizione_id == iscrizione_id, Evidenza.fonte == FonteEvidenza.video_player).first()
        if not ev:
            ev = Evidenza(iscrizione_id=iscrizione_id, fonte=FonteEvidenza.video_player, inizio_at=datetime.now(timezone.utc))
            db.add(ev)
        ev.percentuale_completamento = percentuale
        ev.fine_at = datetime.now(timezone.utc)

    db.commit()
    return {"secondo_massimo_raggiunto": prog.secondo_massimo_raggiunto, "percentuale_completamento": percentuale}

@router.get("/api/iscrizioni/{iscrizione_id}/progresso")
def leggi_progresso(iscrizione_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    prog = db.query(VideoProgresso).filter(VideoProgresso.iscrizione_id == iscrizione_id).first()
    return {"secondo_massimo_raggiunto": prog.secondo_massimo_raggiunto if prog else 0}
