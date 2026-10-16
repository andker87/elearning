"""Elaborazione dei video caricati: piu' qualita' (480p, 720p, 1080p, 4K fino a quella dell'originale),
ognuna cifrata su disco; l'originale viene eliminato a fine lavoro.

Il file originale resta in chiaro solo il tempo della conversione (ffmpeg ha bisogno del file in chiaro);
anche i file di lavoro sono temporanei. Le qualita' pronte si usano subito: il video e' guardabile appena
c'e' la prima, le piu' alte arrivano dopo.
"""
import json
import logging
import os
import shutil
import subprocess
import threading

from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..models.video import StatoVideo, VideoContenuto, VideoVersione
from . import cifratura

log = logging.getLogger(__name__)

PRONTI_DIR = "/app/videos/pronti"
LAVORO_DIR = "/app/videos/lavoro"
TIMEOUT_CODIFICA = 4 * 3600

# altezza -> (CRF, tetto di banda in kbps): il tetto tiene sotto controllo il peso sulla rete
PROFILI = {480: (26, 1000), 720: (24, 2500), 1080: (23, 5000), 2160: (22, 14000)}

_UNA_ALLA_VOLTA = threading.Semaphore(1)   # la conversione e' pesante: un video per volta


def altezze_configurate() -> list:
    valori = []
    for x in (settings.VIDEO_ALTEZZE or "").split(","):
        x = x.strip()
        if x.isdigit() and int(x) in PROFILI:
            valori.append(int(x))
    return sorted(set(valori)) or sorted(PROFILI)


def altezze_da_produrre(altezza_origine: int) -> list:
    """Le qualita' configurate che non superano l'originale (mai ingrandire); se l'originale e' piu' piccolo
    della prima, si produce una sola qualita' alla sua altezza."""
    scelte = [h for h in altezze_configurate() if h <= altezza_origine]
    return scelte or [max(altezza_origine - altezza_origine % 2, 2)]


def profilo(altezza: int) -> tuple:
    if altezza in PROFILI:
        return PROFILI[altezza]
    return 24, max(300, int(5000 * altezza / 1080))


def sonda(percorso: str) -> tuple:
    """(larghezza, altezza, durata in secondi) del file."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
                        "-of", "json", percorso], check=True, capture_output=True, text=True, timeout=120)
    dati = json.loads(r.stdout)
    s = (dati.get("streams") or [{}])[0]
    return int(s.get("width") or 0), int(s.get("height") or 0), float((dati.get("format") or {}).get("duration") or 0)


def _codifica(originale: str, uscita: str, altezza: int):
    crf, tetto = profilo(altezza)
    subprocess.run([
        "ffmpeg", "-y", "-i", originale, "-vf", f"scale=-2:{altezza}", "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-maxrate", f"{tetto}k", "-bufsize", f"{tetto * 2}k",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", uscita,
    ], check=True, capture_output=True, timeout=TIMEOUT_CODIFICA)


def _cifra_in(sorgente: str, destinazione: str):
    with cifratura.Scrittore(destinazione) as s, open(sorgente, "rb") as f:
        while pezzo := f.read(1024 * 1024):
            s.scrivi(pezzo)


def _predefinita(versioni) -> VideoVersione:
    """La qualita' usata quando non se ne sceglie una: la piu' vicina a 720p."""
    return min(versioni, key=lambda x: (abs(x.altezza - 720), x.altezza))


def _produci_versione(db: Session, v: VideoContenuto, originale: str, altezza: int, cartella_lavoro: str):
    os.makedirs(PRONTI_DIR, exist_ok=True)
    temp = os.path.join(cartella_lavoro, f"{altezza}.mp4")
    _codifica(originale, temp, altezza)
    larghezza, h_reale, _ = sonda(temp)
    destinazione = os.path.join(PRONTI_DIR, f"{v.id}_{altezza}p.mp4")
    _cifra_in(temp, destinazione)
    dimensione = os.path.getsize(temp)
    os.remove(temp)
    db.add(VideoVersione(video_id=v.id, altezza=h_reale or altezza, larghezza=larghezza, bitrate_kbps=profilo(altezza)[1],
                         dimensione_bytes=dimensione, file_path=destinazione))
    db.flush()


def transcodifica(video_id: str, originale: str):
    """Gira in sottofondo dopo il caricamento."""
    with _UNA_ALLA_VOLTA:
        db = SessionLocal()
        cartella = os.path.join(LAVORO_DIR, str(video_id))
        v = None
        try:
            v = db.query(VideoContenuto).filter(VideoContenuto.id == video_id).first()
            if not v:
                return
            v.stato = StatoVideo.in_elaborazione
            db.commit()
            os.makedirs(cartella, exist_ok=True)
            _, altezza, durata = sonda(originale)
            if not altezza:
                raise ValueError("il file non contiene un video")
            altezze = altezze_da_produrre(altezza)
            v.durata_secondi = int(durata)
            v.altre_versioni_in_corso = len(altezze) > 1
            db.commit()
            for n, h in enumerate(altezze):
                try:
                    _produci_versione(db, v, originale, h, cartella)
                except Exception:
                    db.rollback()
                    v = db.query(VideoContenuto).filter(VideoContenuto.id == video_id).first()
                    log.exception("conversione a %sp del video %s non riuscita", h, video_id)
                    continue
                db.refresh(v)
                v.file_path = _predefinita(v.versioni).file_path
                v.stato = StatoVideo.pronto            # guardabile dalla prima qualita' pronta
                v.altre_versioni_in_corso = n < len(altezze) - 1
                db.commit()
            if not v.versioni:
                v.stato = StatoVideo.errore
            v.altre_versioni_in_corso = False
            db.commit()
        except Exception:
            db.rollback()
            log.exception("elaborazione del video %s non riuscita", video_id)
            v = db.query(VideoContenuto).filter(VideoContenuto.id == video_id).first()
            if v:
                v.stato = StatoVideo.pronto if v.versioni else StatoVideo.errore
                v.altre_versioni_in_corso = False
                db.commit()
        finally:
            _elimina_originale(db, video_id, originale)
            shutil.rmtree(cartella, ignore_errors=True)
            db.close()


def _elimina_originale(db: Session, video_id: str, originale: str):
    try:
        if originale and os.path.exists(originale):
            os.remove(originale)
        v = db.query(VideoContenuto).filter(VideoContenuto.id == video_id).first()
        if v and v.file_originale:
            v.file_originale = None
            db.commit()
    except Exception:
        db.rollback()
        log.exception("eliminazione dell'originale del video %s non riuscita", video_id)


def recupera_interrotti(db: Session) -> int:
    """All'avvio: i video rimasti a meta' (riavvio durante la conversione) si segnano in errore o pronti se hanno
    gia' una qualita', e gli originali in chiaro rimasti sul disco si eliminano."""
    toccati = 0
    for v in db.query(VideoContenuto).filter(VideoContenuto.file_originale.isnot(None)).all():
        if v.stato in (StatoVideo.caricato, StatoVideo.in_elaborazione):
            v.stato = StatoVideo.pronto if v.versioni else StatoVideo.errore
        v.altre_versioni_in_corso = False
        if os.path.exists(v.file_originale):
            os.remove(v.file_originale)
        v.file_originale = None
        toccati += 1
    for v in db.query(VideoContenuto).filter(VideoContenuto.altre_versioni_in_corso.is_(True)).all():
        v.altre_versioni_in_corso = False
        toccati += 1
    db.commit()
    shutil.rmtree(LAVORO_DIR, ignore_errors=True)   # file temporanei di lavori interrotti
    return toccati
