"""Token di sessione (PyJWT): firma, scadenza e algoritmo sono tutti obbligatori."""
import base64
import json
import time

import jwt

from app.config import settings
from app.services.auth import create_access_token, decode_token


def _senza_firma(payload):
    b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return f"{b({'alg': 'none', 'typ': 'JWT'})}.{b(payload)}."


def test_token_valido_e_scaduto():
    assert decode_token(create_access_token({"sub": "a@test.it"}))["sub"] == "a@test.it"
    assert decode_token(jwt.encode({"sub": "a@test.it", "exp": int(time.time()) - 5}, settings.SECRET_KEY, algorithm="HS256")) is None


def test_token_con_altra_chiave_o_senza_firma_rifiutati():
    assert decode_token(jwt.encode({"sub": "a@test.it"}, "un-altro-segreto-molto-lungo-0123456789", algorithm="HS256")) is None
    assert decode_token(_senza_firma({"sub": "a@test.it", "exp": int(time.time()) + 600})) is None
    assert decode_token("non-un-token") is None


def test_token_con_algoritmo_diverso_rifiutato(client, auth, utente):
    # firmato con un altro algoritmo HMAC con lo stesso segreto: non vale, l'algoritmo ammesso e' uno solo
    t = jwt.encode({"sub": utente.email, "tv": 0, "exp": int(time.time()) + 600}, settings.SECRET_KEY, algorithm="HS512")
    assert decode_token(t) is None
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {t}"}).status_code in (401, 403)
    # confusione tra chiave pubblica e segreto HMAC (la vulnerabilita' di python-jose): non applicabile
    pubblica = b"-----BEGIN PUBLIC KEY-----\nMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE\n-----END PUBLIC KEY-----"
    try:
        falso = jwt.encode({"sub": utente.email, "exp": int(time.time()) + 600}, pubblica, algorithm="HS256")
    except jwt.InvalidKeyError:
        return   # PyJWT rifiuta gia' in partenza una chiave PEM usata come segreto HMAC
    assert decode_token(falso) is None
