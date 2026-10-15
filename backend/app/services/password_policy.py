import re
import secrets

# Policy password unica per tutti i punti che ne impostano una (setup, creazione
# utente, cambio password, reset, import CSV): stessa regola di carpooling e GRC.
# Centralizzata qui: se cambia, cambia una volta sola.
REQUISITI_PASSWORD = "almeno 14 caratteri, con almeno una lettera maiuscola, un numero e un carattere speciale"


def password_valida(password: str) -> bool:
    if not isinstance(password, str) or len(password) < 14:
        return False
    return bool(re.search(r"[A-Z]", password) and re.search(r"[0-9]", password) and re.search(r"[^A-Za-z0-9]", password))


def genera_password_temporanea() -> str:
    """Leggibile e dettabile a voce (niente 0/O, 1/l/I) ma casuale e conforme alla policy."""
    minuscole, maiuscole = "abcdefghjkmnpqrstuvwxyz", "ABCDEFGHJKMNPQRSTUVWXYZ"
    numeri, speciali = "23456789", "!@#$%&*?-_"
    tutti = minuscole + maiuscole + numeri + speciali
    caratteri = [secrets.choice(maiuscole), secrets.choice(numeri), secrets.choice(speciali)]
    caratteri += [secrets.choice(tutti) for _ in range(13)]
    secrets.SystemRandom().shuffle(caratteri)
    return "".join(caratteri)
