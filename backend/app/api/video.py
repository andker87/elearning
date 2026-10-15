import os, uuid, subprocess, json
from datetime import datetime, timezone
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.responses import FileResponse
from jose import jwt, JWTError
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import Optional
from ..config import settings
from ..database import get_db, SessionLocal
from ..models.video import VideoContenuto, VideoCapitolo, VideoProgresso, StatoVideo
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.user import UserRole
from ..models.edizione import Edizione
from ..models.evidenza import Evidenza, FonteEvidenza
from ..services import audit as audit_svc
from .deps import get_current_user, require_training_admin

from .evidenze import SOGLIA_COMPLETAMENTO_VIDEO_PCT  # una sola soglia, condivisa con il completamento delle evidenze

router = APIRouter(tags=["video"])

ORIGINALI_DIR = "/app/videos/originali"
PRONTI_DIR = "/app/videos/pronti"
SOTTOTITOLI_DIR = "/app/videos/sottotitoli"
MAX_VIDEO_BYTES = 2 * 1024 ** 3        # in linea con client_max_body_size di nginx
MAX_SOTTOTITOLI_BYTES = 2 * 1024 ** 2
DURATA_LINK_VIDEO = timedelta(hours=2)  # validita' dell'indirizzo di riproduzione
STATI_CON_ACCESSO = (StatoIscrizione.iscritto, StatoIscrizione.completato, StatoIscrizione.non_completato)

async def _salva_a_pezzi(file: UploadFile, destinazione: str, limite: int):
    """Scrive il file su disco un blocco alla volta (mai intero in memoria) e si ferma
    se supera il limite, senza lasciare file parziali."""
    scritti = 0
    provvisorio = f"{destinazione}.{uuid.uuid4().hex}.parte"   # nome unico: due caricamenti insieme non si mescolano; un nuovo caricamento fallito non distrugge il file precedente
    try:
        with open(provvisorio, "wb") as out:
            while blocco := await file.read(1024 * 1024):
                scritti += len(blocco)
                if scritti > limite:
                    raise HTTPException(413, f"File troppo grande (massimo {limite // (1024 * 1024)} MB)")
                out.write(blocco)
        os.replace(provvisorio, destinazione)
    except BaseException:
        if os.path.exists(provvisorio): os.remove(provvisorio)
        raise

def _serialize(v: VideoContenuto):
    return {
        "id": str(v.id), "titolo": v.titolo, "stato": v.stato,
        "durata_secondi": v.durata_secondi, "ha_file": bool(v.file_path),
        "ha_sottotitoli": bool(v.sottotitoli_path), "blocca_skip_avanti": v.blocca_skip_avanti,
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
    await _salva_a_pezzi(file, path_originale, MAX_VIDEO_BYTES)
    v = VideoContenuto(id=video_id, titolo=titolo, file_originale=path_originale, stato=StatoVideo.caricato)
    db.add(v); db.commit()
    background_tasks.add_task(_transcodifica, str(video_id), path_originale)
    return _serialize(v)

@router.get("/api/video")
def list_video(db: Session = Depends(get_db), user=Depends(require_training_admin)):
    rows = db.query(VideoContenuto).options(joinedload(VideoContenuto.capitoli)).order_by(VideoContenuto.created_at.desc()).all()
    return [_serialize(v) for v in rows]

@router.get("/api/video/{video_id}")
def get_video(video_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = db.query(VideoContenuto).options(joinedload(VideoContenuto.capitoli)).filter(VideoContenuto.id == video_id).first()
    if not v or not _puo_vedere(db, user, v.id): raise HTTPException(404)
    return _serialize(v)

def _puo_vedere(db: Session, user, video_id) -> bool:
    """Chi gestisce la formazione vede tutto; gli altri solo i video delle sessioni a cui sono iscritti."""
    if user.role in (UserRole.admin_tecnico, UserRole.training_admin):
        return True
    return db.query(Iscrizione.id).join(Edizione, Edizione.id == Iscrizione.edizione_id).filter(
        Iscrizione.user_id == user.id, Iscrizione.stato.in_(STATI_CON_ACCESSO), Edizione.video_id == video_id).first() is not None

def _link(video_id: str, tipo: str, user_id: str) -> str:
    scade = datetime.now(timezone.utc) + DURATA_LINK_VIDEO
    token = jwt.encode({"typ": "video", "vid": str(video_id), "k": tipo, "uid": str(user_id), "exp": scade},
                       settings.SECRET_KEY, algorithm="HS256")
    return f"/api/video/{video_id}/{tipo}?t={token}"

@router.get("/api/video/{video_id}/accesso")
def accesso_video(video_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Indirizzi a tempo per guardare il video: senza di essi il file non si apre."""
    v = db.query(VideoContenuto).filter(VideoContenuto.id == video_id).first()
    if not v or not v.file_path or not _puo_vedere(db, user, v.id): raise HTTPException(404)
    return {"video": _link(v.id, "file", user.id),
            "sottotitoli": _link(v.id, "sottotitoli", user.id) if v.sottotitoli_path else None,
            "scade_tra_secondi": int(DURATA_LINK_VIDEO.total_seconds())}

def _servi(db: Session, video_id: str, tipo: str, t: str, media_type: str):
    try:
        dati = jwt.decode(t, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(401, "Indirizzo scaduto o non valido")
    if dati.get("typ") != "video" or dati.get("vid") != video_id or dati.get("k") != tipo:
        raise HTTPException(401, "Indirizzo scaduto o non valido")
    v = db.query(VideoContenuto).filter(VideoContenuto.id == video_id).first()
    if not v: raise HTTPException(404)
    percorso = v.file_path if tipo == "file" else v.sottotitoli_path
    if not percorso or not os.path.isfile(percorso): raise HTTPException(404)
    return FileResponse(percorso, media_type=media_type, headers={"Cache-Control": "private, no-store"})

@router.get("/api/video/{video_id}/file")
def file_video(video_id: str, t: str, db: Session = Depends(get_db)):
    return _servi(db, video_id, "file", t, "video/mp4")

@router.get("/api/video/{video_id}/sottotitoli")
def file_sottotitoli(video_id: str, t: str, db: Session = Depends(get_db)):
    return _servi(db, video_id, "sottotitoli", t, "text/vtt")

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
    await _salva_a_pezzi(file, path, MAX_SOTTOTITOLI_BYTES)
    v.sottotitoli_path = path
    db.commit()
    return {"ok": True}

# --- Tracciamento riproduzione (fonte di evidenza per il completamento) ---

class ProgressoIn(BaseModel):
    secondo_corrente: int

TOLLERANZA_SKIP_SECONDI = 15  # margine per buffering/heartbeat, non un vero "salta avanti"

@router.post("/api/iscrizioni/{iscrizione_id}/progresso")
def aggiorna_progresso(iscrizione_id: str, data: ProgressoIn, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    i = db.query(Iscrizione).filter(Iscrizione.id == iscrizione_id).first()
    if not i or str(i.user_id) != str(user.id):
        raise HTTPException(403, "Iscrizione non valida per l'utente corrente")
    e = db.query(Edizione).filter(Edizione.id == i.edizione_id).first()
    if not e or not e.video_id:
        raise HTTPException(400, "Questa edizione non ha un contenuto video associato")
    video = db.query(VideoContenuto).filter(VideoContenuto.id == e.video_id).first()

    prog = db.query(VideoProgresso).filter(VideoProgresso.iscrizione_id == iscrizione_id).first()
    prima_visione = prog is None
    if not prog:
        prog = VideoProgresso(iscrizione_id=iscrizione_id, secondo_massimo_raggiunto=0)
        db.add(prog); db.flush()
    secondo_precedente = prog.secondo_massimo_raggiunto

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

    # Solo i due momenti che contano per un controllo ispettivo (avvio e
    # superamento della soglia di completamento): l'heartbeat arriva ogni
    # pochi secondi e riempirebbe il registro di rumore.
    soglia = SOGLIA_COMPLETAMENTO_VIDEO_PCT
    pct_prima = (min(100.0, secondo_precedente / video.durata_secondi * 100) if video.durata_secondi else 0)
    nome_ed = audit_svc.nome_edizione(db, e)
    if prima_visione:
        audit_svc.log_from_request(db, request, user, "VIDEO_AVVIATO", entity_type="edizione", entity_id=str(e.id),
                                    entity_name=nome_ed, detail=f"video: {video.titolo}")
    if percentuale is not None and pct_prima < soglia <= percentuale:
        audit_svc.log_from_request(db, request, user, "VIDEO_COMPLETATO", entity_type="edizione", entity_id=str(e.id),
                                    entity_name=nome_ed, detail=f"video: {video.titolo} - raggiunto il {percentuale}%")

    db.commit()
    return {"secondo_massimo_raggiunto": prog.secondo_massimo_raggiunto, "percentuale_completamento": percentuale}

@router.get("/api/iscrizioni/{iscrizione_id}/progresso")
def leggi_progresso(iscrizione_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    prog = db.query(VideoProgresso).filter(VideoProgresso.iscrizione_id == iscrizione_id).first()
    return {"secondo_massimo_raggiunto": prog.secondo_massimo_raggiunto if prog else 0}
