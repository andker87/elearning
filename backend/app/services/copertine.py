"""Copertine dei corsi.

Un'immagine per corso, caricata dalla Formazione. Il file caricato si controlla (formato, dimensione, pixel), si raddrizza se il
telefono l'ha ruotata, si ritaglia al centro nel formato 16:9 e si riduce a 1280x720 al massimo: nessuna copertina rompe
l'impaginazione e nessuna pesa troppo. Si conserva cifrata come gli altri file e si mostra con un indirizzo firmato a tempo
(un'immagine in una pagina non puo' portare l'intestazione di accesso)."""
import hashlib
import io
import os
import time
import uuid
from typing import Optional

import jwt
from jwt import PyJWTError
from PIL import Image, ImageOps

from ..config import settings
from . import cifratura

CARTELLA = "/app/uploads/copertine"
FORMATI = ("image/png", "image/jpeg", "image/webp")
MAX_BYTE = 5 * 1024 * 1024
MAX_PIXEL = 25_000_000
MIN_LARGHEZZA, MIN_ALTEZZA = 640, 360
LARGHEZZA, ALTEZZA = 1280, 720
FINESTRA_LINK = 6 * 3600          # i link valgono tra 6 e 12 ore e per tutto il periodo sono identici: il browser tiene l'immagine in memoria


class CopertinaNonValida(ValueError):
    pass


def prepara(contenuto: bytes) -> bytes:
    """Controlla l'immagine e la restituisce pronta: JPEG 16:9, al massimo 1280x720."""
    if len(contenuto) > MAX_BYTE:
        raise CopertinaNonValida("Il file è troppo grande (massimo 5 MB)")
    try:
        img = Image.open(io.BytesIO(contenuto))
        larghezza, altezza = img.size
        if larghezza * altezza > MAX_PIXEL:
            raise CopertinaNonValida("L'immagine è troppo grande (massimo 25 megapixel)")
        img.load()                                     # decodifica completa: un file rotto si scopre qui
    except CopertinaNonValida:
        raise
    except Exception:
        raise CopertinaNonValida("Il file non è un'immagine valida")
    img = ImageOps.exif_transpose(img)
    larghezza, altezza = img.size
    if larghezza < MIN_LARGHEZZA or altezza < MIN_ALTEZZA:
        raise CopertinaNonValida(f"L'immagine è troppo piccola: servono almeno {MIN_LARGHEZZA}x{MIN_ALTEZZA} pixel (meglio {LARGHEZZA}x{ALTEZZA})")
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        sfondo = Image.new("RGB", img.size, (255, 255, 255))      # le trasparenze diventano bianco
        sfondo.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
        img = sfondo
    else:
        img = img.convert("RGB")
    # ritaglio centrale al formato 16:9
    rapporto = LARGHEZZA / ALTEZZA
    if larghezza / altezza > rapporto:
        nuova = int(round(altezza * rapporto)); x = (larghezza - nuova) // 2
        img = img.crop((x, 0, x + nuova, altezza))
    else:
        nuova = int(round(larghezza / rapporto)); y = (altezza - nuova) // 2
        img = img.crop((0, y, larghezza, y + nuova))
    if img.size[0] > LARGHEZZA:
        img = img.resize((LARGHEZZA, ALTEZZA), Image.Resampling.LANCZOS)
    uscita = io.BytesIO()
    img.save(uscita, "JPEG", quality=85, optimize=True, progressive=True)
    return uscita.getvalue()


def salva(corso, contenuto_grezzo: bytes) -> None:
    pronto = prepara(contenuto_grezzo)
    os.makedirs(CARTELLA, exist_ok=True)
    percorso = os.path.join(CARTELLA, f"{corso.id}-{uuid.uuid4().hex[:12]}.jpg")   # mai sopra quella vecchia: si toglie solo dopo il commit
    cifratura.scrivi_file(percorso, pronto)
    corso.copertina_path = percorso
    corso.copertina_v = hashlib.sha256(pronto).hexdigest()[:10]       # cambia con l'immagine: serve a non vedere la vecchia in memoria


def rimuovi_file(percorso: Optional[str]) -> None:
    try:
        if percorso and os.path.isfile(percorso):
            os.remove(percorso)
    except OSError:
        pass


def _token(corso_id: str) -> str:
    finestra = int(time.time() // FINESTRA_LINK)
    return jwt.encode({"typ": "copertina", "cid": str(corso_id), "exp": (finestra + 2) * FINESTRA_LINK}, settings.SECRET_KEY, algorithm="HS256")


def url(corso) -> Optional[str]:
    """L'indirizzo (firmato) con cui la pagina mostra la copertina; None se il corso non ne ha."""
    if not getattr(corso, "copertina_path", None):
        return None
    return f"/api/corsi/{corso.id}/copertina?t={_token(corso.id)}&v={corso.copertina_v or ''}"


def token_valido(token: str, corso_id: str) -> bool:
    try:
        dati = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except PyJWTError:
        return False
    return dati.get("typ") == "copertina" and dati.get("cid") == str(corso_id)
