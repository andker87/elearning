"""SSO OpenID Connect contro un provider finto (chiavi RSA vere, discovery, JWKS, token endpoint)."""
import base64
import hashlib
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import jwt

from app.config import settings
from app.models.audit import AuditLog
from app.models.user import User, UserRole
from app.services import sso as sso_svc

from conftest import PASSWORD


def nuova_chiave():
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(k.public_key(), as_dict=True)
    jwk.update({"kid": "k1", "use": "sig", "alg": "RS256"})
    return pem, jwk


class FakeIdp:
    def __init__(self):
        self.chiave, self.jwk = nuova_chiave()
        self.altra_chiave, _ = nuova_chiave()
        self.codici = {}
        idp = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, o, code=200):
                b = json.dumps(o).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                if self.path.endswith("openid-configuration"):
                    self._json({"issuer": idp.issuer, "authorization_endpoint": idp.issuer + "/authorize",
                                "token_endpoint": idp.issuer + "/token", "jwks_uri": idp.issuer + "/jwks"})
                elif self.path == "/jwks":
                    self._json({"keys": [idp.jwk]})
                else:
                    self._json({}, 404)

            def do_POST(self):
                f = parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
                c = idp.codici.pop(f["code"][0], None)
                if not c or f["client_secret"][0] != "segreto":
                    return self._json({"error": "invalid_grant"}, 400)
                challenge = base64.urlsafe_b64encode(hashlib.sha256(f["code_verifier"][0].encode()).digest()).rstrip(b"=").decode()
                if challenge != c["challenge"]:
                    return self._json({"error": "pkce"}, 400)
                claims = {**c["claims"], "iss": idp.issuer, "aud": c.get("aud", "client-test"), "iat": int(time.time()),
                          "exp": int(time.time()) + 300, "nonce": c["nonce"] + c.get("nonce_suffix", "")}
                self._json({"id_token": jwt.encode(claims, c.get("key", idp.chiave), algorithm="RS256", headers={"kid": "k1"})})

        self.server = HTTPServer(("127.0.0.1", 0), H)
        self.issuer = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


@pytest.fixture(scope="module")
def idp():
    i = FakeIdp()
    yield i
    i.server.shutdown()


@pytest.fixture
def sso(idp, pulizia, monkeypatch):
    for k, v in {"SSO_ISSUER": idp.issuer, "SSO_CLIENT_ID": "client-test", "SSO_CLIENT_SECRET": "segreto",
                 "SSO_PUBLIC_URL": "http://testserver"}.items():
        monkeypatch.setattr(settings, k, v)
    sso_svc._cache.update(disc=None, disc_at=0.0, jwks=None, jwks_at=0.0)
    return idp


def accedi(client, idp, claims, aud=None, key=None, nonce_suffix="", state=None, senza_cookie=False, challenge_ok=True):
    r = client.get("/api/auth/sso/login")
    assert r.status_code == 302
    q = parse_qs(urlparse(r.headers["location"]).query)
    code = uuid.uuid4().hex
    idp.codici[code] = {"claims": claims, "nonce": q["nonce"][0], "challenge": q["code_challenge"][0] if challenge_ok else "x",
                        "nonce_suffix": nonce_suffix, **({"aud": aud} if aud else {}), **({"key": key} if key else {})}
    if senza_cookie:
        client.cookies.clear()
    r = client.get("/api/auth/sso/callback", params={"code": code, "state": state or q["state"][0]})
    loc = r.headers.get("location", "")
    if "#sso_token=" in loc:
        return "OK", loc.split("#sso_token=")[1]
    return parse_qs(urlparse(loc).query).get("sso_errore", ["?"])[0], None


def test_redirect_con_pkce_state_e_nonce(client, sso):
    r = client.get("/api/auth/sso/login")
    q = parse_qs(urlparse(r.headers["location"]).query)
    assert r.headers["location"].startswith(sso.issuer + "/authorize")
    assert q["code_challenge_method"] == ["S256"] and "state" in q and "nonce" in q
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_config_non_configurato(client):
    assert client.get("/api/auth/sso/config").json()["enabled"] is False
    assert client.get("/api/auth/sso/login").status_code in (302, 400, 404)


def test_primo_collegamento_per_email_senza_distinguere_maiuscole(client, db, sso, crea_utente, auth):
    u = crea_utente("mario@test.it")
    esito, token = accedi(client, sso, {"sub": "sub-1", "email": "Mario@Test.IT"})
    assert esito == "OK"
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["email"] == u.email
    db.refresh(u)
    assert u.sso_subject == "sub-1" and u.origine_credenziali == "dominio"
    # da qui conta il sub, anche se l'email cambia
    assert accedi(client, sso, {"sub": "sub-1", "email": "cambiata@test.it"})[0] == "OK"


def test_con_sso_attivo_la_password_vale_solo_per_locali_e_admin(client, sso, crea_utente):
    dominio = crea_utente("dom@test.it", origine_credenziali="dominio")
    assert client.post("/api/auth/login", json={"email": dominio.email, "password": PASSWORD}).status_code == 401
    admin_dominio = crea_utente("adm@test.it", UserRole.admin_tecnico, origine_credenziali="dominio")
    assert client.post("/api/auth/login", json={"email": admin_dominio.email, "password": PASSWORD}).status_code == 200  # accesso di emergenza
    locale = crea_utente("loc@test.it")
    assert client.post("/api/auth/login", json={"email": locale.email, "password": PASSWORD}).status_code == 200


@pytest.mark.parametrize("nome,opzioni,atteso", [
    ("firmato con un'altra chiave", {"key": "altra"}, "token_non_valido"),
    ("audience sbagliata", {"aud": "altro-client"}, "token_non_valido"),
    ("nonce sbagliato", {"nonce_suffix": "X"}, "token_non_valido"),
    ("state manomesso", {"state": "falso"}, "state_non_valido"),
    ("cookie assente", {"senza_cookie": True}, "sessione_scaduta"),
    ("PKCE verifier errato", {"challenge_ok": False}, "scambio_codice"),
])
def test_attacchi_respinti(client, sso, crea_utente, nome, opzioni, atteso):
    crea_utente("vittima@test.it")
    if opzioni.get("key") == "altra":
        opzioni = {**opzioni, "key": sso.altra_chiave}
    assert accedi(client, sso, {"sub": "s", "email": "vittima@test.it"}, **opzioni)[0] == atteso, nome


def test_callback_senza_transazione(client, sso):
    r = client.get("/api/auth/sso/callback", params={"code": "riuso", "state": "x"})
    assert "sessione_scaduta" in r.headers["location"]


@pytest.mark.parametrize("claims,utente_kw,atteso", [
    ({"sub": "s", "email": "u@test.it", "email_verified": False}, {}, "email_non_verificata"),
    ({"sub": "s"}, {}, "email_assente"),
    ({"sub": "s", "email": "sconosciuto@test.it"}, None, "utente_non_abilitato"),
    ({"sub": "intruso", "email": "u@test.it"}, {"sso_subject": "originale"}, "identita_diversa"),
    ({"sub": "s", "email": "u@test.it"}, {"is_active": False}, "utente_disabilitato"),
    ({"sub": "s", "email": "u@test.it"}, {"is_external": True}, "esterno_non_ammesso"),
])
def test_utenti_non_ammessi(client, sso, crea_utente, claims, utente_kw, atteso):
    if utente_kw is not None:
        crea_utente("u@test.it", **utente_kw)
    assert accedi(client, sso, claims)[0] == atteso


def test_provisioning_crea_l_utente_solo_se_abilitato(client, db, sso, monkeypatch):
    claims = {"sub": "nuovo", "email": "nuovo@test.it", "name": "Nuovo Utente"}
    assert accedi(client, sso, claims)[0] == "utente_non_abilitato"
    monkeypatch.setattr(settings, "SSO_PROVISIONA_UTENTI", True)
    assert accedi(client, sso, claims)[0] == "OK"
    u = db.query(User).filter(User.email == "nuovo@test.it").one()
    assert u.role == UserRole.user and u.origine_credenziali == "dominio" and u.full_name == "Nuovo Utente" and u.sso_subject == "nuovo"


def test_audit_di_accessi_e_rifiuti(client, db, sso, crea_utente):
    crea_utente("ok@test.it")
    accedi(client, sso, {"sub": "s", "email": "ok@test.it"})
    accedi(client, sso, {"sub": "altro-sub", "email": "sconosciuto@test.it"})
    assert db.query(AuditLog).filter(AuditLog.action == "LOGIN", AuditLog.detail.ilike("SSO%")).count() == 1
    assert db.query(AuditLog).filter(AuditLog.action == "SSO_LOGIN_FAILED").count() == 1


def test_admin_tecnico_non_si_collega_per_email_ma_chi_e_gia_collegato_entra(client, db, sso, crea_utente):
    adm = crea_utente("admin@az.it", UserRole.admin_tecnico)
    assert accedi(client, sso, {"sub": "admin-sub", "email": "admin@az.it"})[0] == "admin_non_collegabile"
    db.refresh(adm)
    assert adm.sso_subject is None
    adm.sso_subject = "admin-sub"   # collegamento fatto dall'amministrazione di sistema
    db.commit()
    assert accedi(client, sso, {"sub": "admin-sub", "email": "admin@az.it"})[0] == "OK"


def test_accetta_id_token_con_at_hash(client, sso, crea_utente):
    """Google, Keycloak e Okta mettono at_hash nell'id_token: non deve far fallire l'accesso."""
    crea_utente("conhash@test.it")
    assert accedi(client, sso, {"sub": "h1", "email": "conhash@test.it", "at_hash": "qualcosa"})[0] == "OK"
