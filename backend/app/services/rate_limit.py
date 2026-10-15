import threading
import time
from collections import defaultdict, deque

_lock = threading.Lock()
_eventi = defaultdict(deque)
_MAX_CHIAVI = 5000


def _pulisci(coda, ora, finestra):
    while coda and ora - coda[0] > finestra:
        coda.popleft()


def _potatura(ora, finestra):
    """Le chiavi nascono anche da input non autenticato (es. email): oltre una soglia si scartano
    quelle ormai vuote o scadute, cosi' la memoria non cresce senza limite."""
    if len(_eventi) <= _MAX_CHIAVI:
        return
    for k in [k for k, c in _eventi.items() if not c or ora - c[-1] > finestra]:
        del _eventi[k]


def superato(chiave: str, limite: int, finestra_secondi: int) -> bool:
    """Il limite e' gia' raggiunto? Non registra nulla."""
    ora = time.monotonic()
    with _lock:
        coda = _eventi.get(chiave)
        if coda is None:
            return False
        _pulisci(coda, ora, finestra_secondi)
        if not coda:
            del _eventi[chiave]
            return False
        return len(coda) >= limite


def registra(chiave: str, finestra_secondi: int = 3600):
    ora = time.monotonic()
    with _lock:
        _potatura(ora, finestra_secondi)
        _eventi[chiave].append(ora)


def consenti(chiave: str, limite: int, finestra_secondi: int) -> bool:
    """Finestra scorrevole in memoria, per singolo processo: registra il tentativo e dice se
    rientra nel limite."""
    ora = time.monotonic()
    with _lock:
        _potatura(ora, finestra_secondi)
        coda = _eventi[chiave]
        _pulisci(coda, ora, finestra_secondi)
        if len(coda) >= limite:
            return False
        coda.append(ora)
        return True
