"""Impronte per cercare i dati personali cifrati.

Il testo cifrato cambia a ogni cifratura, quindi nel database non si puo' cercare "l'utente con questa email".
Si conserva accanto una impronta: HMAC-SHA256 del valore (senza maiuscole e spazi ai lati) con una chiave
propria. Con la stessa chiave lo stesso valore da' la stessa impronta, quindi la ricerca esatta funziona;
senza la chiave dell'impronta non si risale al valore.
La chiave delle impronte e' casuale, generata una volta e conservata nel database (azienda.impronta_chiave),
cifrata con CHIAVE_CIFRATURA se c'e'. Non dipende dalla chiave di cifratura: cambiare quella (rotazione) non
cambia le impronte e non obbliga a ricalcolarle."""
import hashlib
import hmac
import secrets
import threading
from typing import Optional

from ..database import SessionLocal
from ..models.azienda import Azienda
from . import cifratura

_blocco = threading.Lock()
_chiave: Optional[bytes] = None


def _leggi_o_crea() -> bytes:
    db = SessionLocal()
    try:
        a = db.query(Azienda).with_for_update().first()   # il blocco sulla riga evita due chiavi create insieme
        if not a:
            a = Azienda()
            db.add(a)
            db.flush()
        if not a.impronta_chiave:
            a.impronta_chiave = cifratura.cifra_testo(secrets.token_hex(32))
            db.commit()
        return bytes.fromhex(cifratura.decifra_testo(a.impronta_chiave))
    finally:
        db.close()


def calcola(chiave: bytes, valore: Optional[str]) -> Optional[str]:
    if valore is None:
        return None
    return hmac.new(chiave, valore.strip().lower().encode(), hashlib.sha256).hexdigest()


def assicura() -> None:
    """Carica (o crea) la chiave delle impronte: si chiama all'avvio, cosi' un problema si vede subito."""
    global _chiave
    with _blocco:
        if _chiave is None:
            _chiave = _leggi_o_crea()


def impronta(valore: Optional[str]) -> Optional[str]:
    if valore is None:
        return None
    assicura()
    return calcola(_chiave, valore)
