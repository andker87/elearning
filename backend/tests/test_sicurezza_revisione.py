"""Regressioni emerse dalla revisione del codice."""
from datetime import timedelta

from app.api.password_reset import RICHIESTE_PER_EMAIL
from app.config import settings
from app.models.azienda import Azienda
from app.models.user import User, UserRole

from conftest import PASSWORD, adesso


def attiva_smtp(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(settings, "SMTP_MITTENTE", "noreply@test.it")
    inviate = []
    monkeypatch.setattr("app.api.password_reset.invia_email", lambda a, o, c: inviate.append((a, o, c)) or True)
    return inviate


# --- il link di reset non si costruisce con dati della richiesta -----------------------------

def test_header_origin_falso_non_finisce_nel_link(client, db, utente, monkeypatch):
    inviate = attiva_smtp(monkeypatch)
    client.post("/api/auth/password-dimenticata", json={"email": utente.email}, headers={"Origin": "https://evil.example"})
    assert inviate == []  # nessun URL configurato: niente link, la richiesta va all'Admin tecnico


def test_link_solo_con_l_url_configurato(client, db, utente, monkeypatch):
    inviate = attiva_smtp(monkeypatch)
    db.add(Azienda(url_pubblico="https://formazione.acme.it"))
    db.commit()
    client.post("/api/auth/password-dimenticata", json={"email": utente.email}, headers={"Origin": "https://evil.example"})
    assert len(inviate) == 1 and "https://formazione.acme.it/reimposta-password?token=" in inviate[0][2] and "evil" not in inviate[0][2]


def test_limite_per_email_anche_cambiando_indirizzo(client, db, utente, monkeypatch):
    inviate = attiva_smtp(monkeypatch)
    db.add(Azienda(url_pubblico="https://f.acme.it"))
    db.commit()
    for n in range(RICHIESTE_PER_EMAIL + 4):
        client.post("/api/auth/password-dimenticata", json={"email": utente.email}, headers={"X-Forwarded-For": f"10.0.0.{n}"})
    assert len(inviate) == RICHIESTE_PER_EMAIL


# --- email senza distinzione di maiuscole -----------------------------------------------------

def test_login_e_reset_ignorano_le_maiuscole(client, crea_utente, monkeypatch):
    u = crea_utente("Mario.Rossi@Azienda.it")
    assert client.post("/api/auth/login", json={"email": "mario.rossi@azienda.it", "password": PASSWORD}).status_code == 200
    inviate = attiva_smtp(monkeypatch)
    from app.models.azienda import Azienda as A
    monkeypatch.setattr(settings, "SSO_PUBLIC_URL", "https://f.acme.it")
    client.post("/api/auth/password-dimenticata", json={"email": "MARIO.ROSSI@azienda.it"})
    assert len(inviate) == 1


def test_non_si_creano_due_utenti_che_differiscono_per_le_maiuscole(client, admin, auth, crea_utente):
    crea_utente("a@x.it")
    r = client.post("/api/auth/users", headers=auth(admin), json={"email": "A@x.it", "full_name": "Doppione", "password": PASSWORD})
    assert r.status_code == 400


# --- import cessati: scelta esplicita ---------------------------------------------------------

def test_il_nome_del_file_non_attiva_la_disattivazione(client, db, admin, auth, crea_utente):
    u = crea_utente("resta@az.it")
    r = client.post("/api/auth/users/import-csv", headers=auth(admin), files={"file": ("cessata_formazione_nuovi.csv", b"email,full_name\nresta@az.it,X\n", "text/csv")})
    assert r.status_code == 400 and "cessati" in r.json()["detail"]
    db.refresh(u)
    assert u.is_active


def test_i_cessati_non_includono_gli_admin_tecnici(client, db, admin, auth, crea_utente):
    altro_admin = crea_utente("altro.admin@az.it", UserRole.admin_tecnico)
    normale = crea_utente("esce@az.it")
    r = client.post("/api/auth/users/import-csv", headers=auth(admin), params={"modo": "cessati"},
                    files={"file": ("e.csv", b"email\naltro.admin@az.it\nesce@az.it\n", "text/csv")}).json()
    esiti = {x["email"]: x["esito"] for x in r["righe"]}
    assert esiti == {"altro.admin@az.it": "errore", "esce@az.it": "disattivato"}
    db.refresh(altro_admin); db.refresh(normale)
    assert altro_admin.is_active and not normale.is_active


# --- calendario e struttura dei responsabili ---------------------------------------------------

def test_feed_calendario_dopo_la_disattivazione(client, db, utente):
    utente.calendar_token = "tok-calendario"
    db.commit()
    assert client.get("/api/calendario/feed.ics", params={"token": "tok-calendario"}).status_code == 200
    utente.is_active = False
    db.commit()
    assert client.get("/api/calendario/feed.ics", params={"token": "tok-calendario"}).status_code == 404


def test_struttura_dei_responsabili_solo_per_se_stessi_o_formazione(client, auth, utente, formazione, crea_utente):
    altro = crea_utente("altro@test.it")
    for percorso in ("sottoposti", "uffici-guidati", "responsabili"):
        assert client.get(f"/api/auth/users/{utente.id}/{percorso}", headers=auth(utente)).status_code == 200
        assert client.get(f"/api/auth/users/{altro.id}/{percorso}", headers=auth(utente)).status_code == 403
        assert client.get(f"/api/auth/users/{altro.id}/{percorso}", headers=auth(formazione)).status_code == 200


# --- SSO e Admin tecnico ------------------------------------------------------------------------

def test_sso_non_collega_per_email_un_admin_tecnico():
    from app.api import sso
    import inspect
    assert "admin_non_collegabile" in inspect.getsource(sso._risolvi_utente)


# --- cambio password obbligatorio imposto dal server ----------------------------------------------

def test_con_password_assegnata_si_puo_solo_cambiarla(client, auth, crea_utente):
    u = crea_utente(password_da_cambiare=True)
    h = auth(u)
    assert client.get("/api/auth/me", headers=h).status_code == 200
    assert client.get("/api/privacy/informativa", headers=h).status_code == 403
    assert client.get("/api/edizioni", headers=h).status_code == 403
    r = client.put("/api/auth/me/password", headers=h, json={"current_password": PASSWORD, "new_password": "Scelta!DaMe12345"})
    assert r.status_code == 200
    nuovo = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/privacy/informativa", headers=nuovo).status_code == 200


def test_chi_usa_il_dominio_non_e_bloccato_dal_cambio_password(client, auth, crea_utente):
    u = crea_utente(password_da_cambiare=True, origine_credenziali="dominio")
    assert client.get("/api/privacy/informativa", headers=auth(u)).status_code == 200
