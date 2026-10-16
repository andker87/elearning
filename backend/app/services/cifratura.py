"""Cifratura a riposo dei file e dei segreti nel database.

Formato dei file cifrati (versione 1), a blocchi cosi' da poter leggere solo una parte (utile per i video):
    intestazione (20 byte): "ELC1" | id chiave (4) | prefisso nonce (8) | dimensione blocco in chiaro (4)
    blocchi: AES-256-GCM(blocco in chiaro, fino a 64 KB) = testo cifrato + 16 byte di autenticazione
Il nonce di ogni blocco e' prefisso + numero del blocco; i dati autenticati comprendono intestazione,
numero del blocco e un indicatore "ultimo blocco": un blocco alterato, spostato o un file troncato non si decifra.

Chiavi: CHIAVE_CIFRATURA (corrente, 32 byte in base64) e CHIAVI_CIFRATURA_PRECEDENTI (elenco, solo per leggere
file scritti prima di un cambio di chiave). La chiave di ogni scopo (file, database) deriva dalla chiave principale.
Un file che non inizia con la firma "ELC1" e' in chiaro e si legge cosi' com'e': la conversione e' graduale.
"""
import base64
import hashlib
import io
import os
import struct
import uuid

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from ..config import settings

MAGIC = b"ELC1"
BLOCCO = 64 * 1024
TAG = 16
INTESTAZIONE = 20
PREFISSO_TESTO = "enc:v1:"


class ErroreCifratura(Exception):
    pass


class ChiaveMancante(ErroreCifratura):
    """Il file e' cifrato con una chiave che questa installazione non ha."""


class ContenutoNonValido(ErroreCifratura):
    """File alterato, troncato o non decifrabile."""


# --- chiavi -----------------------------------------------------------------------------------

def _decodifica(valore: str) -> bytes:
    try:
        chiave = base64.urlsafe_b64decode(valore.strip() + "=" * (-len(valore.strip()) % 4))
    except Exception:
        raise ErroreCifratura("La chiave di cifratura non e' in base64")
    if len(chiave) != 32:
        raise ErroreCifratura("La chiave di cifratura deve essere di 32 byte (in base64)")
    return chiave


def _kid(principale: bytes) -> bytes:
    return hashlib.sha256(principale).digest()[:4]


def _derivata(principale: bytes, scopo: bytes) -> bytes:
    return HKDF(algorithm=SHA256(), length=32, salt=None, info=b"elearning-" + scopo).derive(principale)


def _chiavi_note() -> dict:
    """id chiave -> chiave principale, per la corrente e le precedenti."""
    note = {}
    for testo in [settings.CHIAVE_CIFRATURA] + (settings.CHIAVI_CIFRATURA_PRECEDENTI or "").split(","):
        if testo and testo.strip():
            principale = _decodifica(testo)
            note[_kid(principale)] = principale
    return note


def attiva() -> bool:
    return bool(settings.CHIAVE_CIFRATURA and settings.CHIAVE_CIFRATURA.strip())


def _corrente() -> tuple:
    principale = _decodifica(settings.CHIAVE_CIFRATURA)
    return _kid(principale), principale


def id_chiave_corrente() -> str:
    return _corrente()[0].hex() if attiva() else None


def genera_chiave() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def _chiave_per(kid: bytes, scopo: bytes) -> bytes:
    principale = _chiavi_note().get(kid)
    if principale is None:
        raise ChiaveMancante(f"Il contenuto e' cifrato con la chiave {kid.hex()}, che non e' configurata")
    return _derivata(principale, scopo)


# --- file -------------------------------------------------------------------------------------

def e_cifrato(inizio: bytes) -> bool:
    return inizio[:4] == MAGIC


def _nonce(prefisso: bytes, n: int) -> bytes:
    return prefisso + struct.pack(">I", n)


def _aad(intestazione: bytes, n: int, ultimo: bool) -> bytes:
    return intestazione + struct.pack(">I", n) + (b"\x01" if ultimo else b"\x00")


class Scrittore:
    """Scrive un file un blocco alla volta (mai intero in memoria). Con la cifratura attiva scrive il formato
    cifrato, altrimenti il file in chiaro. Il file compare al suo posto solo alla chiusura riuscita."""

    def __init__(self, percorso: str, cifra: bool = None):
        """`cifra` None = segue la configurazione; False forza il file in chiaro (usato dalla conversione inversa)."""
        self.percorso = percorso
        self._tmp = f"{percorso}.{uuid.uuid4().hex}.parte"
        os.makedirs(os.path.dirname(percorso) or ".", exist_ok=True)
        self._f = open(self._tmp, "wb")
        self._cifra = attiva() if cifra is None else (cifra and attiva())
        self._buf = bytearray()
        self._n = 0
        self.scritti = 0   # byte in chiaro
        if self._cifra:
            kid, principale = _corrente()
            self._aes = AESGCM(_derivata(principale, b"file-v1"))
            prefisso = os.urandom(8)
            self._intestazione = MAGIC + kid + prefisso + struct.pack(">I", BLOCCO)
            self._prefisso = prefisso
            self._f.write(self._intestazione)

    def scrivi(self, dati: bytes):
        self.scritti += len(dati)
        if not self._cifra:
            self._f.write(dati)
            return
        self._buf += dati
        while len(self._buf) > BLOCCO:   # l'ultimo blocco resta nel buffer: va marcato come ultimo
            self._blocco(bytes(self._buf[:BLOCCO]), False)
            del self._buf[:BLOCCO]

    def _blocco(self, dati: bytes, ultimo: bool):
        self._f.write(self._aes.encrypt(_nonce(self._prefisso, self._n), dati, _aad(self._intestazione, self._n, ultimo)))
        self._n += 1

    def chiudi(self):
        if self._cifra:
            self._blocco(bytes(self._buf), True)
            self._buf.clear()
        self._f.close()
        os.replace(self._tmp, self.percorso)

    def annulla(self):
        if not self._f.closed:
            self._f.close()
        if os.path.exists(self._tmp):
            os.remove(self._tmp)

    def __enter__(self):
        return self

    def __exit__(self, tipo, valore, tb):
        if tipo is None:
            self.chiudi()
        else:
            self.annulla()
        return False


def scrivi_file(percorso: str, dati: bytes, cifra: bool = None):
    with Scrittore(percorso, cifra) as s:
        s.scrivi(dati)


async def salva_upload(file, percorso: str, limite: int, errore) -> int:
    """Salva un caricamento (UploadFile) a pezzi, cifrandolo se serve. `errore(limite)` costruisce l'eccezione
    da sollevare se supera il limite. Ritorna i byte salvati."""
    s = Scrittore(percorso)
    try:
        while blocco := await file.read(1024 * 1024):
            if s.scritti + len(blocco) > limite:
                raise errore(limite)
            s.scrivi(blocco)
        s.chiudi()
        return s.scritti
    except BaseException:
        s.annulla()
        raise


def _leggi_intestazione(f):
    intest = f.read(INTESTAZIONE)
    if len(intest) < INTESTAZIONE or intest[:4] != MAGIC:
        raise ContenutoNonValido("Intestazione non valida")
    return intest, intest[4:8], intest[8:16], struct.unpack(">I", intest[16:20])[0]


def _decifra_blocco(aes, intest, prefisso, n, cifrato, ultimo):
    try:
        return aes.decrypt(_nonce(prefisso, n), cifrato, _aad(intest, n, ultimo))
    except InvalidTag:
        raise ContenutoNonValido("Il file e' alterato o incompleto")


def leggi_file(percorso: str) -> bytes:
    """Contenuto in chiaro del file: lo decifra se e' cifrato, altrimenti lo restituisce cosi' com'e'."""
    with open(percorso, "rb") as f:
        inizio = f.read(4)
        f.seek(0)
        if not e_cifrato(inizio):
            return f.read()
        intest, kid, prefisso, blocco = _leggi_intestazione(f)
        aes = AESGCM(_chiave_per(kid, b"file-v1"))
        totale = os.fstat(f.fileno()).st_size
        out, n, pos = io.BytesIO(), 0, INTESTAZIONE
        while True:
            lung = min(blocco + TAG, totale - pos)
            if lung < TAG:
                raise ContenutoNonValido("File troncato")
            ultimo = pos + lung >= totale
            out.write(_decifra_blocco(aes, intest, prefisso, n, f.read(lung), ultimo))
            n += 1
            pos += lung
            if ultimo:
                return out.getvalue()


def leggi_intervallo(percorso: str, inizio: int, fine: int) -> bytes:
    """Byte [inizio, fine] (estremi inclusi) del contenuto in chiaro, decifrando solo i blocchi necessari."""
    with open(percorso, "rb") as f:
        if not e_cifrato(f.read(4)):
            f.seek(inizio)
            return f.read(fine - inizio + 1)
        f.seek(0)
        intest, kid, prefisso, blocco = _leggi_intestazione(f)
        aes = AESGCM(_chiave_per(kid, b"file-v1"))
        totale = os.fstat(f.fileno()).st_size
        out = bytearray()
        for n in range(inizio // blocco, fine // blocco + 1):
            pos = INTESTAZIONE + n * (blocco + TAG)
            if pos >= totale:
                break
            lung = min(blocco + TAG, totale - pos)
            f.seek(pos)
            chiaro = _decifra_blocco(aes, intest, prefisso, n, f.read(lung), pos + lung >= totale)
            da = max(inizio - n * blocco, 0)
            a = min(fine - n * blocco + 1, len(chiaro))
            out += chiaro[da:a]
        return bytes(out)


def dimensione_in_chiaro(percorso: str) -> int:
    with open(percorso, "rb") as f:
        if not e_cifrato(f.read(4)):
            return os.path.getsize(percorso)
        f.seek(0)
        _, _, _, blocco = _leggi_intestazione(f)
        resto = os.path.getsize(percorso) - INTESTAZIONE
        interi, ultimo = divmod(resto, blocco + TAG)
        return interi * blocco + max(ultimo - TAG, 0)


def stato_file(percorso: str) -> str:
    """'cifrato', 'chiaro' oppure 'cifrato con altra chiave' (da ruotare)."""
    with open(percorso, "rb") as f:
        intest = f.read(INTESTAZIONE)
    if not e_cifrato(intest):
        return "chiaro"
    if attiva() and intest[4:8] == _corrente()[0]:
        return "cifrato"
    return "altra_chiave"


# --- testi (segreti nel database) ---------------------------------------------------------------

def cifra_testo(testo: str) -> str:
    if testo is None or not attiva() or testo.startswith(PREFISSO_TESTO):
        return testo
    kid, principale = _corrente()
    nonce = os.urandom(12)
    ct = AESGCM(_derivata(principale, b"db-v1")).encrypt(nonce, testo.encode(), kid)
    return PREFISSO_TESTO + kid.hex() + ":" + base64.urlsafe_b64encode(nonce + ct).decode()


def decifra_testo(valore: str) -> str:
    """Il testo in chiaro; un valore non cifrato (installazione senza cifratura o non ancora convertito) torna uguale."""
    if valore is None or not valore.startswith(PREFISSO_TESTO):
        return valore
    try:
        _, _, kid_hex, dati = valore.split(":", 3)
        kid, dati = bytes.fromhex(kid_hex), base64.urlsafe_b64decode(dati)
    except Exception:
        raise ContenutoNonValido("Valore cifrato non valido")
    try:
        return AESGCM(_chiave_per(kid, b"db-v1")).decrypt(dati[:12], dati[12:], kid).decode()
    except InvalidTag:
        raise ContenutoNonValido("Il valore cifrato e' alterato")


def testo_e_cifrato(valore: str) -> bool:
    return bool(valore) and valore.startswith(PREFISSO_TESTO)


def testo_con_chiave_corrente(valore: str) -> bool:
    return testo_e_cifrato(valore) and attiva() and valore.split(":", 3)[2] == _corrente()[0].hex()
