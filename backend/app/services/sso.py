import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

import httpx
from jose import jwt, JWTError

from ..config import settings

COOKIE_TXN = "sso_txn"
TXN_DURATA_SECONDI = 600
_cache = {"disc": None, "disc_at": 0.0, "jwks": None, "jwks_at": 0.0}
CACHE_SECONDI = 3600


class SsoErrore(Exception):
    """Errore di accesso SSO: il codice breve finisce nell'URL di ritorno e nell'audit."""
    def __init__(self, codice: str, dettaglio: str = ""):
        super().__init__(codice)
        self.codice = codice
        self.dettaglio = dettaglio


def redirect_uri() -> str:
    return settings.SSO_PUBLIC_URL.rstrip("/") + "/api/auth/sso/callback"


def _get(url: str) -> dict:
    r = httpx.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def discovery() -> dict:
    if not _cache["disc"] or time.time() - _cache["disc_at"] > CACHE_SECONDI:
        base = settings.SSO_ISSUER.rstrip("/")
        _cache["disc"] = _get(base + "/.well-known/openid-configuration")
        _cache["disc_at"] = time.time()
    return _cache["disc"]


def _jwks(forza: bool = False) -> dict:
    if forza or not _cache["jwks"] or time.time() - _cache["jwks_at"] > CACHE_SECONDI:
        _cache["jwks"] = _get(discovery()["jwks_uri"])
        _cache["jwks_at"] = time.time()
    return _cache["jwks"]


def nuova_transazione() -> dict:
    """Valori monouso del singolo tentativo di login: finiscono in un cookie
    HttpOnly firmato (verifier e nonce non devono passare dall'URL)."""
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return {"state": secrets.token_urlsafe(24), "nonce": secrets.token_urlsafe(24),
            "verifier": verifier, "challenge": challenge}


def url_autorizzazione(txn: dict) -> str:
    params = {
        "client_id": settings.SSO_CLIENT_ID, "response_type": "code",
        "redirect_uri": redirect_uri(), "scope": "openid email profile",
        "state": txn["state"], "nonce": txn["nonce"],
        "code_challenge": txn["challenge"], "code_challenge_method": "S256",
    }
    return discovery()["authorization_endpoint"] + "?" + urlencode(params)


def firma_transazione(txn: dict) -> str:
    payload = {"state": txn["state"], "nonce": txn["nonce"], "verifier": txn["verifier"],
               "exp": int(time.time()) + TXN_DURATA_SECONDI}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def leggi_transazione(cookie: str) -> dict:
    try:
        return jwt.decode(cookie, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise SsoErrore("sessione_scaduta", "cookie di transazione assente, scaduto o manomesso")


def scambia_codice(code: str, verifier: str) -> str:
    r = httpx.post(discovery()["token_endpoint"], timeout=10, data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri(),
        "client_id": settings.SSO_CLIENT_ID, "client_secret": settings.SSO_CLIENT_SECRET,
        "code_verifier": verifier,
    })
    if r.status_code != 200:
        raise SsoErrore("scambio_codice", f"token endpoint ha risposto {r.status_code}")
    id_token = r.json().get("id_token")
    if not id_token:
        raise SsoErrore("scambio_codice", "id_token assente nella risposta")
    return id_token


def verifica_id_token(id_token: str, nonce_atteso: str) -> dict:
    """Firma (RS256 dal JWKS dell'IdP), issuer, audience, scadenza e nonce."""
    try:
        header = jwt.get_unverified_header(id_token)
    except JWTError:
        raise SsoErrore("token_non_valido", "id_token malformato")
    if header.get("alg") != "RS256":
        raise SsoErrore("token_non_valido", f"algoritmo non ammesso: {header.get('alg')}")

    def _decodifica(jwks):
        # at_hash: molti IdP (Google, Keycloak, Okta) lo mettono nell'id_token e python-jose lo pretende
        # insieme all'access token. Qui l'id_token arriva direttamente dal token endpoint via TLS e
        # non si usa l'access token: la verifica non aggiunge nulla e farebbe fallire ogni accesso.
        return jwt.decode(id_token, jwks, algorithms=["RS256"], audience=settings.SSO_CLIENT_ID,
                          issuer=discovery()["issuer"], options={"verify_at_hash": False})
    try:
        try:
            claims = _decodifica(_jwks())
        except JWTError:
            # chiave ruotata dall'IdP: un solo ricaricamento del JWKS, poi errore vero
            claims = _decodifica(_jwks(forza=True))
    except JWTError as e:
        raise SsoErrore("token_non_valido", str(e)[:200])
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce_atteso):
        raise SsoErrore("token_non_valido", "nonce non corrispondente")
    return claims


def email_da_claims(claims: dict) -> str:
    email = claims.get("email") or claims.get("preferred_username") or claims.get("upn") or ""
    email = str(email).strip().lower()
    if "@" not in email:
        raise SsoErrore("email_assente", "l'IdP non ha fornito un indirizzo email")
    if claims.get("email_verified") is False:
        raise SsoErrore("email_non_verificata", email)
    return email
