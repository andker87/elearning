"""Sicurezza degli accessi: policy password, blocco, sessioni, reset."""
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.models.password_reset import PasswordResetToken, RichiestaResetPassword
from app.models.user import User
from app.services.rate_limit import consenti

from conftest import PASSWORD


def login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_creazione_utente_rispetta_la_policy_password(client, admin, auth, crea_ufficio):
    uff = str(crea_ufficio().id)
    for debole in ["corta1!A", "senzamaiuscola1!aaaa", "SenzaNumero!!!!!!", "SenzaSpeciale12345A"]:
        r = client.post("/api/auth/users", headers=auth(admin), json={"email": "n@test.it", "full_name": "N", "password": debole, "ufficio_id": uff})
        assert r.status_code == 400, debole
    r = client.post("/api/auth/users", headers=auth(admin), json={"email": "n@test.it", "full_name": "N", "password": PASSWORD, "ufficio_id": uff})
    assert r.status_code == 200
    assert r.json()["password_da_cambiare"] is True  # password scelta da altri


def test_login_errato_non_rivela_nulla(client, utente):
    assert login(client, utente.email, "sbagliata").status_code == 401
    assert login(client, "nessuno@test.it", "sbagliata").status_code == 401


def test_account_sospeso_dopo_cinque_tentativi_e_si_sblocca(client, db, utente):
    for _ in range(5):
        assert login(client, utente.email, "sbagliata").status_code == 401
    assert login(client, utente.email, PASSWORD).status_code == 401   # nemmeno la password giusta, finche' e' sospeso
    db.query(User).filter(User.id == utente.id).update({"bloccato_fino": datetime.now(timezone.utc) - timedelta(seconds=1)})
    db.commit()
    assert login(client, utente.email, PASSWORD).status_code == 200
    db.refresh(utente)
    assert utente.tentativi_falliti == 0 and utente.bloccato_fino is None


def test_la_risposta_non_rivela_se_l_email_esiste_o_se_e_sospesa(client, utente):
    ignoto = login(client, "nessuno@test.it", "x")
    sbagliata = login(client, utente.email, "x")
    for _ in range(4):
        login(client, utente.email, "x")
    sospeso = login(client, utente.email, PASSWORD)
    assert ignoto.status_code == sbagliata.status_code == sospeso.status_code == 401
    assert ignoto.json() == sbagliata.json() == sospeso.json()


def test_il_blocco_e_segnalato_agli_admin_tecnici_una_volta_all_ora(client, db, admin, utente):
    from app.models.notification import Notification
    for _ in range(5):
        login(client, utente.email, "x")
    db.query(User).filter(User.id == utente.id).update({"bloccato_fino": None})
    db.commit()
    for _ in range(5):
        login(client, utente.email, "x")
    avvisi = db.query(Notification).filter(Notification.user_id == admin.id, Notification.tipo == "account_bloccato").all()
    assert len(avvisi) == 1 and utente.email in avvisi[0].testo


def test_il_reset_della_password_toglie_la_sospensione(client, db, admin, auth, utente):
    for _ in range(5):
        login(client, utente.email, "x")
    client.post("/api/auth/password-dimenticata", json={"email": utente.email})
    rid = client.get("/api/auth/password-reset-richieste", headers=auth(admin)).json()["richieste"][0]["id"]
    temporanea = client.post(f"/api/auth/password-reset-richieste/{rid}/genera", headers=auth(admin)).json()["password_temporanea"]
    assert login(client, utente.email, temporanea).status_code == 200


def test_un_login_riuscito_azzera_i_tentativi(client, db, utente):
    for _ in range(3):
        login(client, utente.email, "sbagliata")
    assert login(client, utente.email, PASSWORD).status_code == 200
    for _ in range(4):
        assert login(client, utente.email, "sbagliata").status_code == 401  # riparte da zero, non blocca


def test_limite_per_indirizzo(client):
    codici = [login(client, f"x{i}@test.it", "x").status_code for i in range(32)]
    assert codici[:30] == [401] * 30
    assert codici[30] == 429


def test_finestra_scorrevole():
    assert [consenti("k", 2, 60) for _ in range(3)] == [True, True, False]
    assert consenti("altra", 2, 60) is True


def test_cambio_password_chiude_le_altre_sessioni(client, utente, auth):
    vecchio = auth(utente)
    corpo = {"current_password": PASSWORD, "new_password": "Nuova!Password456"}
    assert client.put("/api/auth/me/password", headers=vecchio, json={**corpo, "new_password": "debole"}).status_code == 400
    assert client.put("/api/auth/me/password", headers=vecchio, json={**corpo, "new_password": PASSWORD}).status_code == 400
    r = client.put("/api/auth/me/password", headers=vecchio, json=corpo)
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=vecchio).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).status_code == 200
    assert login(client, utente.email, "Nuova!Password456").status_code == 200


def test_cambio_obbligatorio_si_spegne_dopo_il_cambio(client, crea_utente, auth):
    u = crea_utente(password_da_cambiare=True)
    assert client.get("/api/auth/me", headers=auth(u)).json()["password_da_cambiare"] is True
    r = client.put("/api/auth/me/password", headers=auth(u), json={"current_password": PASSWORD, "new_password": "Scelta!DaMe12345"})
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).json()["password_da_cambiare"] is False


def test_cambio_obbligatorio_non_riguarda_chi_usa_il_dominio(client, crea_utente, auth):
    u = crea_utente(password_da_cambiare=True, origine_credenziali="dominio")
    assert client.get("/api/auth/me", headers=auth(u)).json()["password_da_cambiare"] is False


def test_password_assegnata_da_admin_forza_il_cambio_e_chiude_sessioni(client, admin, utente, auth):
    vecchio = auth(utente)
    r = client.put(f"/api/auth/users/{utente.id}", headers=auth(admin), json={"password": "Assegnata!Da1Admin"})
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=vecchio).status_code == 401
    assert client.put(f"/api/auth/users/{utente.id}", headers=auth(admin), json={"password": "debole"}).status_code == 400


# --- password dimenticata ----------------------------------------------------------------

def attiva_smtp(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(settings, "SMTP_MITTENTE", "noreply@test.it")
    inviate = []
    monkeypatch.setattr("app.api.password_reset.invia_email", lambda a, o, c: inviate.append((a, o, c)) or True)
    return inviate


def imposta_url(db, url="https://formazione.test"):
    from app.models.azienda import Azienda
    db.add(Azienda(url_pubblico=url))
    db.commit()


def test_reset_via_email_link_monouso(client, db, utente, monkeypatch):
    inviate = attiva_smtp(monkeypatch)
    imposta_url(db)
    r = client.post("/api/auth/password-dimenticata", json={"email": utente.email})
    assert r.json() == {"ok": True}
    assert len(inviate) == 1 and inviate[0][0] == utente.email
    token = inviate[0][2].split("token=")[1].split()[0]
    assert inviate[0][2].count("https://formazione.test/reimposta-password?token=") == 1

    assert client.post("/api/auth/reimposta-password", json={"token": token, "password_nuova": "debole"}).status_code == 400
    assert client.post("/api/auth/reimposta-password", json={"token": token, "password_nuova": "Reimpostata!Ok123"}).status_code == 200
    assert client.post("/api/auth/reimposta-password", json={"token": token, "password_nuova": "Altra!Password123"}).status_code == 400  # riuso
    assert login(client, utente.email, "Reimpostata!Ok123").status_code == 200


def test_reset_token_scaduto_o_falso(client, db, utente, monkeypatch):
    import hashlib
    db.add(PasswordResetToken(user_id=utente.id, token_hash=hashlib.sha256(b"vecchio").hexdigest(),
                              scade_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
    db.commit()
    for t in ("vecchio", "inventato"):
        assert client.post("/api/auth/reimposta-password", json={"token": t, "password_nuova": "Reimpostata!Ok123"}).status_code == 400


def test_reset_sblocca_un_account_bloccato(client, db, utente, monkeypatch):
    inviate = attiva_smtp(monkeypatch)
    imposta_url(db, "https://f.test")
    for _ in range(5):
        login(client, utente.email, "x")
    client.post("/api/auth/password-dimenticata", json={"email": utente.email})
    token = inviate[0][2].split("token=")[1].split()[0]
    client.post("/api/auth/reimposta-password", json={"token": token, "password_nuova": "Reimpostata!Ok123"})
    assert login(client, utente.email, "Reimpostata!Ok123").status_code == 200


def test_reset_senza_smtp_passa_all_admin(client, db, admin, utente, auth):
    assert client.post("/api/auth/password-dimenticata", json={"email": utente.email}).json() == {"ok": True}
    client.post("/api/auth/password-dimenticata", json={"email": utente.email})  # doppione: una sola richiesta
    assert db.query(RichiestaResetPassword).count() == 1

    assert client.get("/api/auth/password-reset-richieste", headers=auth(utente)).status_code == 403
    lista = client.get("/api/auth/password-reset-richieste", headers=auth(admin)).json()
    assert lista["smtp_attivo"] is False and len(lista["richieste"]) == 1
    rid = lista["richieste"][0]["id"]

    vecchio = auth(utente)
    r = client.post(f"/api/auth/password-reset-richieste/{rid}/genera", headers=auth(admin))
    temporanea = r.json()["password_temporanea"]
    assert client.post(f"/api/auth/password-reset-richieste/{rid}/genera", headers=auth(admin)).status_code == 400
    assert client.get("/api/auth/me", headers=vecchio).status_code == 401
    accesso = login(client, utente.email, temporanea)
    assert accesso.status_code == 200 and accesso.json()["user"]["password_da_cambiare"] is True


def test_reset_non_rivela_chi_e_registrato_e_ignora_dominio_e_disattivi(client, db, crea_utente, monkeypatch):
    inviate = attiva_smtp(monkeypatch)
    dominio = crea_utente("dominio@test.it", origine_credenziali="dominio")
    disattivo = crea_utente("off@test.it", is_active=False)
    for email in ("nessuno@test.it", dominio.email, disattivo.email):
        r = client.post("/api/auth/password-dimenticata", json={"email": email})
        assert r.json() == {"ok": True}
    assert inviate == [] and db.query(RichiestaResetPassword).count() == 0
