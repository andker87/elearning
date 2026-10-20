import os, re, uuid
from datetime import datetime, timezone
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.responses import Response, StreamingResponse
import jwt
from jwt import PyJWTError as JWTError
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload
from pydantic import BaseModel
from typing import Optional
from ..config import settings
from ..database import get_db, SessionLocal
from ..models.video import VideoContenuto, VideoCapitolo, VideoProgresso, StatoVideo
from ..models.iscrizione import Iscrizione, StatoIscrizione
from ..models.edizione import Edizione, EdizioneDocente
from ..models.evidenza import Evidenza, FonteEvidenza
from ..services import audit as audit_svc
from ..services import cifratura
from ..services import video_elaborazione
from .deps import get_current_user, require_training_admin

from ..services.completamento import completa_se_dovuto
from ..services.iscrizioni import disponibilita_video
from .evidenze import SOGLIA_COMPLETAMENTO_VIDEO_PCT  # una sola soglia, condivisa con il completamento delle evidenze

router = APIRouter(tags=["video"])

ORIGINALI_DIR = "/app/videos/originali"
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

def _usi_dei_video(db: Session, ids=None) -> dict:
    """In quante sessioni e' collegato ciascun video (una query per tutti)."""
    q = db.query(Edizione.video_id, func.count(Edizione.id)).filter(Edizione.video_id.isnot(None))
    if ids is not None:
        q = q.filter(Edizione.video_id.in_(ids))
    return dict(q.group_by(Edizione.video_id).all())

def _serialize(v: VideoContenuto, usato_in: int = 0):
    return {
        "id": str(v.id), "titolo": v.titolo, "stato": v.stato,
        "durata_secondi": v.durata_secondi, "ha_file": bool(v.file_path),
        "ha_sottotitoli": bool(v.sottotitoli_path), "blocca_skip_avanti": v.blocca_skip_avanti,
        "usato_in": usato_in,
        "qualita": [x.altezza for x in sorted(v.versioni, key=lambda x: x.altezza)],
        "altre_qualita_in_preparazione": bool(v.altre_versioni_in_corso),
        "capitoli": [{"id": str(c.id), "titolo": c.titolo, "inizio_secondi": c.inizio_secondi}
                     for c in sorted(v.capitoli, key=lambda x: x.inizio_secondi)],
    }

@router.post("/api/video")
async def upload_video(background_tasks: BackgroundTasks, titolo: str = Form(...),
                        file: UploadFile = File(...), db: Session = Depends(get_db),
                        user=Depends(require_training_admin)):
    os.makedirs(ORIGINALI_DIR, exist_ok=True)
    video_id = uuid.uuid4()
    ext = os.path.splitext(file.filename or "")[1]
    ext = ext if re.fullmatch(r"\.[A-Za-z0-9]{1,5}", ext) else ".mp4"   # solo un'estensione semplice: il nome arriva dall'utente
    path_originale = os.path.join(ORIGINALI_DIR, f"{video_id}{ext}")
    await _salva_a_pezzi(file, path_originale, MAX_VIDEO_BYTES)
    v = VideoContenuto(id=video_id, titolo=titolo, file_originale=path_originale, stato=StatoVideo.caricato)
    db.add(v); db.commit()
    background_tasks.add_task(video_elaborazione.transcodifica, str(video_id), path_originale)
    return _serialize(v)

@router.get("/api/video")
def list_video(db: Session = Depends(get_db), user=Depends(require_training_admin)):
    rows = db.query(VideoContenuto).options(joinedload(VideoContenuto.capitoli), selectinload(VideoContenuto.versioni)).order_by(VideoContenuto.created_at.desc()).all()
    usi = _usi_dei_video(db)
    return [_serialize(v, usi.get(v.id, 0)) for v in rows]

@router.get("/api/video/{video_id}")
def get_video(video_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    v = db.query(VideoContenuto).options(joinedload(VideoContenuto.capitoli), selectinload(VideoContenuto.versioni)).filter(VideoContenuto.id == video_id).first()
    if not v or not _puo_vedere(db, user, v.id): raise HTTPException(404)
    return _serialize(v, _usi_dei_video(db, [v.id]).get(v.id, 0))

def _gestisce_video(db: Session, user, video_id) -> bool:
    """Chi gestisce la formazione, o e' docente di una sessione con questo video: lo vede sempre (anche in anteprima)."""
    if user.ha_poteri_formazione:
        return True
    return db.query(EdizioneDocente.id).join(Edizione, Edizione.id == EdizioneDocente.edizione_id).filter(
        EdizioneDocente.user_id == user.id, Edizione.video_id == video_id).first() is not None


def _aperto_a_chi_segue(db: Session, user, video_id) -> Optional[str]:
    """Chi segue il corso guarda il video solo nel periodo della sessione (da quando inizia, fino alla fine se c'e').
    None = si puo' guardare ora; altrimenti il motivo («non_ancora» / «scaduto»)."""
    sessioni = (db.query(Edizione).join(Iscrizione, Iscrizione.edizione_id == Edizione.id)
                .filter(Iscrizione.user_id == user.id, Iscrizione.stato.in_(STATI_CON_ACCESSO), Edizione.video_id == video_id).all())
    motivi = []
    for e in sessioni:
        d = disponibilita_video(e)
        if d["ok"]:
            return None
        motivi.append(d["motivo"])
    return "non_ancora" if "non_ancora" in motivi else (motivi[0] if motivi else None)


def _puo_vedere(db: Session, user, video_id) -> bool:
    """Chi gestisce la formazione vede tutto; i docenti di una sessione vedono il suo video (anche in anteprima);
    gli altri solo i video delle sessioni a cui sono iscritti."""
    if _gestisce_video(db, user, video_id):
        return True
    return db.query(Iscrizione.id).join(Edizione, Edizione.id == Iscrizione.edizione_id).filter(
        Iscrizione.user_id == user.id, Iscrizione.stato.in_(STATI_CON_ACCESSO), Edizione.video_id == video_id).first() is not None

def _link(video_id: str, tipo: str, user_id: str, altezza: int = 0) -> str:
    scade = datetime.now(timezone.utc) + DURATA_LINK_VIDEO
    token = jwt.encode({"typ": "video", "vid": str(video_id), "k": tipo, "h": altezza, "uid": str(user_id), "exp": scade},
                       settings.SECRET_KEY, algorithm="HS256")
    if tipo == "file":
        return f"/api/video/{video_id}/file/{altezza}?t={token}"
    return f"/api/video/{video_id}/{tipo}?t={token}"

@router.get("/api/video/{video_id}/accesso")
def accesso_video(video_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Indirizzi a tempo per guardare il video, uno per ogni qualita': senza di essi il file non si apre."""
    v = db.query(VideoContenuto).options(joinedload(VideoContenuto.versioni)).filter(VideoContenuto.id == video_id).first()
    if not v or not v.file_path or not _puo_vedere(db, user, v.id): raise HTTPException(404)
    if not _gestisce_video(db, user, v.id):
        motivo = _aperto_a_chi_segue(db, user, v.id)
        if motivo:
            raise HTTPException(403, "Il video sarà disponibile all'inizio della sessione" if motivo == "non_ancora" else "Il video non è più disponibile: la sessione è terminata")
    versioni = sorted(v.versioni, key=lambda x: x.altezza)
    if versioni:
        predefinita = next((x for x in versioni if x.file_path == v.file_path), versioni[0])
        elenco = [{"altezza": x.altezza, "bitrate_kbps": x.bitrate_kbps, "url": _link(v.id, "file", user.id, x.altezza)} for x in versioni]
    else:   # video caricato prima delle qualita' multiple: un solo file
        predefinita = None
        elenco = [{"altezza": 0, "bitrate_kbps": None, "url": _link(v.id, "file", user.id, 0)}]
    return {"video": _link(v.id, "file", user.id, predefinita.altezza if predefinita else 0), "versioni": elenco,
            "sottotitoli": _link(v.id, "sottotitoli", user.id) if v.sottotitoli_path else None,
            "scade_tra_secondi": int(DURATA_LINK_VIDEO.total_seconds())}

def _verifica_indirizzo(video_id: str, tipo: str, t: str) -> dict:
    try:
        dati = jwt.decode(t, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(401, "Indirizzo scaduto o non valido")
    if dati.get("typ") != "video" or dati.get("vid") != video_id or dati.get("k") != tipo:
        raise HTTPException(401, "Indirizzo scaduto o non valido")
    return dati

def _risposta_a_intervalli(request: Request, percorso: str, media_type: str):
    """Invia il file (decifrato al volo) rispettando le richieste parziali del player: chi guarda da remoto
    scarica solo cio' che serve e puo' saltare avanti e indietro."""
    totale = cifratura.dimensione_in_chiaro(percorso)
    intestazioni = {"Accept-Ranges": "bytes", "Cache-Control": "private, no-store"}
    richiesta = (request.headers.get("range") or "").strip()
    m = re.fullmatch(r"bytes=(\d*)-(\d*)", richiesta) if richiesta else None
    if not m or (m.group(1) == "" and m.group(2) == "") or totale == 0:
        intestazioni["Content-Length"] = str(totale)
        return StreamingResponse(cifratura.scorri_intervallo(percorso, 0, totale - 1) if totale else iter(()), media_type=media_type, headers=intestazioni)
    if m.group(1) == "":                       # ultimi N byte
        inizio, fine = max(totale - int(m.group(2)), 0), totale - 1
    else:
        inizio = int(m.group(1))
        fine = min(int(m.group(2)), totale - 1) if m.group(2) else totale - 1
    if inizio >= totale or inizio > fine:
        return Response(status_code=416, headers={**intestazioni, "Content-Range": f"bytes */{totale}"})
    intestazioni.update({"Content-Range": f"bytes {inizio}-{fine}/{totale}", "Content-Length": str(fine - inizio + 1)})
    return StreamingResponse(cifratura.scorri_intervallo(percorso, inizio, fine), status_code=206, media_type=media_type, headers=intestazioni)

@router.get("/api/video/{video_id}/file")
@router.get("/api/video/{video_id}/file/{altezza}")
def file_video(video_id: str, request: Request, t: str, altezza: Optional[int] = None, db: Session = Depends(get_db)):
    dati = _verifica_indirizzo(video_id, "file", t)
    if altezza is not None and altezza != dati.get("h"):
        raise HTTPException(401, "Indirizzo scaduto o non valido")
    h = dati.get("h", 0) if altezza is None else altezza
    v = db.query(VideoContenuto).options(joinedload(VideoContenuto.versioni)).filter(VideoContenuto.id == video_id).first()
    if not v: raise HTTPException(404)
    percorso = next((x.file_path for x in v.versioni if x.altezza == h), None) if h else v.file_path
    if not percorso or not os.path.isfile(percorso): raise HTTPException(404)
    return _risposta_a_intervalli(request, percorso, "video/mp4")

@router.get("/api/video/{video_id}/sottotitoli")
def file_sottotitoli(video_id: str, t: str, db: Session = Depends(get_db)):
    _verifica_indirizzo(video_id, "sottotitoli", t)
    v = db.query(VideoContenuto).filter(VideoContenuto.id == video_id).first()
    if not v or not v.sottotitoli_path or not os.path.isfile(v.sottotitoli_path): raise HTTPException(404)
    return Response(cifratura.leggi_file(v.sottotitoli_path), media_type="text/vtt", headers={"Cache-Control": "private, no-store"})

class VideoUpdate(BaseModel):
    blocca_skip_avanti: Optional[bool] = None
    titolo: Optional[str] = None

@router.put("/api/video/{video_id}")
def update_video(video_id: str, data: VideoUpdate, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    v = db.query(VideoContenuto).filter(VideoContenuto.id == video_id).first()
    if not v: raise HTTPException(404)
    if data.blocca_skip_avanti is not None: v.blocca_skip_avanti = data.blocca_skip_avanti
    if data.titolo is not None:
        if not data.titolo.strip(): raise HTTPException(400, "Il titolo non può essere vuoto")
        v.titolo = data.titolo.strip()
    db.commit()
    return {"ok": True}

class CapitoloIn(BaseModel):
    titolo: str
    inizio_secondi: int

def _controlla_capitolo(v: VideoContenuto, data: CapitoloIn) -> str:
    titolo = data.titolo.strip()
    if not titolo: raise HTTPException(400, "Il titolo del capitolo non può essere vuoto")
    if data.inizio_secondi < 0: raise HTTPException(400, "L'inizio del capitolo non può essere negativo")
    if v.durata_secondi and data.inizio_secondi > v.durata_secondi:
        raise HTTPException(400, "L'inizio del capitolo è oltre la fine del video")
    return titolo

@router.post("/api/video/{video_id}/capitoli")
def add_capitolo(video_id: str, data: CapitoloIn, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    v = db.query(VideoContenuto).filter(VideoContenuto.id == video_id).first()
    if not v:
        raise HTTPException(404)
    c = VideoCapitolo(video_id=video_id, titolo=_controlla_capitolo(v, data), inizio_secondi=data.inizio_secondi)
    db.add(c); db.commit()
    return {"ok": True, "id": str(c.id)}

@router.put("/api/video/{video_id}/capitoli/{capitolo_id}")
def update_capitolo(video_id: str, capitolo_id: str, data: CapitoloIn, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    v = db.query(VideoContenuto).filter(VideoContenuto.id == video_id).first()
    c = db.query(VideoCapitolo).filter(VideoCapitolo.id == capitolo_id, VideoCapitolo.video_id == video_id).first()
    if not v or not c: raise HTTPException(404)
    c.titolo = _controlla_capitolo(v, data)
    c.inizio_secondi = data.inizio_secondi
    db.commit()
    return {"ok": True}

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
    await cifratura.salva_upload(file, path, MAX_SOTTOTITOLI_BYTES, lambda lim: HTTPException(413, f"File troppo grande (massimo {lim // (1024 * 1024)} MB)"))
    v.sottotitoli_path = path
    db.commit()
    return {"ok": True}

@router.delete("/api/video/{video_id}/sottotitoli")
def elimina_sottotitoli(video_id: str, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    v = db.query(VideoContenuto).filter(VideoContenuto.id == video_id).first()
    if not v: raise HTTPException(404)
    if v.sottotitoli_path:
        _rimuovi_file(v.sottotitoli_path)
        v.sottotitoli_path = None
        db.commit()
    return {"ok": True}

def _rimuovi_file(percorso):
    try:
        if percorso and os.path.isfile(percorso):
            os.remove(percorso)
    except OSError:
        pass   # un file gia' sparito o non rimovibile non deve impedire di togliere il video dall'elenco

@router.delete("/api/video/{video_id}")
def elimina_video(video_id: str, request: Request, db: Session = Depends(get_db), user=Depends(require_training_admin)):
    """Si elimina solo un video che nessuna sessione usa: togliere un video collegato lascerebbe sessioni senza contenuto."""
    v = db.query(VideoContenuto).options(selectinload(VideoContenuto.versioni)).filter(VideoContenuto.id == video_id).first()
    if not v: raise HTTPException(404)
    usi = _usi_dei_video(db, [v.id]).get(v.id, 0)
    if usi:
        raise HTTPException(400, f"Il video è collegato a {usi} {'sessione' if usi == 1 else 'sessioni'}: scollegalo prima dalle sessioni (o elimina le sessioni)")
    # L'elaborazione parte dopo il caricamento e puo' continuare a produrre qualita' piu' alte anche a video pronto:
    # eliminare in uno di questi momenti lascerebbe file orfani o farebbe fallire il lavoro in corso.
    # (Se un riavvio la interrompe, all'avvio il video viene sistemato e di nuovo eliminabile.)
    if v.stato in (StatoVideo.caricato, StatoVideo.in_elaborazione) or v.altre_versioni_in_corso:
        raise HTTPException(400, "Il video è in elaborazione: attendi che finisca")
    file_da_togliere = [v.file_originale, v.file_path, v.sottotitoli_path] + [x.file_path for x in v.versioni]
    audit_svc.log_from_request(db, request, user, "DELETE", entity_type="video", entity_id=str(v.id), entity_name=v.titolo)
    db.delete(v)       # capitoli e versioni cadono con lui
    db.commit()
    for percorso in set(p for p in file_da_togliere if p):
        _rimuovi_file(percorso)
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
    if not disponibilita_video(e)["ok"]:
        raise HTTPException(403, "Il video non è disponibile in questo momento")

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

    certificato = None
    if percentuale is not None and percentuale >= soglia:
        db.flush()
        certificato = completa_se_dovuto(db, request, i)         # sessione sempre aperta: completata e attestato subito
    db.commit()
    return {"secondo_massimo_raggiunto": prog.secondo_massimo_raggiunto, "percentuale_completamento": percentuale,
            "completato": certificato is not None, "certificato_id": str(certificato.id) if certificato else None}

@router.get("/api/iscrizioni/{iscrizione_id}/progresso")
def leggi_progresso(iscrizione_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    prog = db.query(VideoProgresso).filter(VideoProgresso.iscrizione_id == iscrizione_id).first()
    return {"secondo_massimo_raggiunto": prog.secondo_massimo_raggiunto if prog else 0}
