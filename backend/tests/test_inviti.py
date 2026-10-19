"""Nuovi utenti: link per scegliere la password invece della password per email."""
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.models.azienda import Azienda
from app.models.password_reset import PasswordResetToken
from app.models.user import User

from conftest import PASSWORD

BUONA = "Scelta!DallAdmin12"


def canale(db, monkeypatch, attivo=True):
    inviate = []
    if attivo:
        monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test")
        monkeypatch.setattr(settings, "SMTP_MITTENTE", "noreply@test.it")
        db.add(Azienda(url_pubblico="https://formazione.acme.it"))
        db.commit()
    monkeypatch.setattr("app.services.inviti.invia_email", lambda a, o, c: inviate.append((a, o, c)) or True)
    return inviate


def crea(client, admin, auth, **extra):
    return client.post("/api/auth/users", headers=auth(admin), json={"email": "nuovo@test.it", "nome": "Nuova", "cognome": "Persona", "is_admin": True, **extra})


def test_con_email_attiva_arriva_un_link_e_nessuna_password(client, db, admin, auth, monkeypatch):
    inviate = canale(db, monkeypatch)
    r = crea(client, admin, auth)
    assert r.status_code == 200 and r.json()["invito_inviato"] is True and r.json()["password_temporanea"] is None
    assert len(inviate) == 1 and inviate[0][0] == "nuovo@test.it"
    corpo = inviate[0][2]
    assert "https://formazione.acme.it/reimposta-password?token=" in corpo and "Password:" not in corpo
    token = corpo.split("token=")[1].split()[0]
    assert client.post("/api/auth/reimposta-password", json={"token": token, "password_nuova": BUONA}).status_code == 200
    accesso = client.post("/api/auth/login", json={"email": "nuovo@test.it", "password": BUONA})
    assert accesso.status_code == 200 and accesso.json()["user"]["password_da_cambiare"] is False


def test_il_link_dura_tre_giorni_ed_e_monouso(client, db, admin, auth, monkeypatch):
    inviate = canale(db, monkeypatch)
    crea(client, admin, auth)
    t = db.query(PasswordResetToken).one()
    durata = t.scade_at - datetime.now(timezone.utc)
    assert timedelta(hours=71) < durata < timedelta(hours=73)
    token = inviate[0][2].split("token=")[1].split()[0]
    assert client.post("/api/auth/reimposta-password", json={"token": token, "password_nuova": BUONA}).status_code == 200
    assert client.post("/api/auth/reimposta-password", json={"token": token, "password_nuova": "Altra!Password99"}).status_code == 400


def test_la_password_scelta_dall_admin_non_viaggia_per_email(client, db, admin, auth, monkeypatch):
    inviate = canale(db, monkeypatch)
    r = crea(client, admin, auth, password=BUONA)
    assert r.json()["invito_inviato"] is True and r.json()["password_temporanea"] is None
    assert BUONA not in inviate[0][2]
    accesso = client.post("/api/auth/login", json={"email": "nuovo@test.it", "password": BUONA})
    assert accesso.status_code == 200 and accesso.json()["user"]["password_da_cambiare"] is True


def test_senza_email_l_admin_riceve_una_password_temporanea_una_volta(client, db, admin, auth, monkeypatch):
    canale(db, monkeypatch, attivo=False)
    r = crea(client, admin, auth).json()
    assert r["invito_inviato"] is False and r["password_temporanea"]
    accesso = client.post("/api/auth/login", json={"email": "nuovo@test.it", "password": r["password_temporanea"]})
    assert accesso.status_code == 200 and accesso.json()["user"]["password_da_cambiare"] is True
    assert db.query(PasswordResetToken).count() == 0


def test_con_password_scelta_e_senza_email_non_si_rimostra(client, db, admin, auth, monkeypatch):
    canale(db, monkeypatch, attivo=False)
    r = crea(client, admin, auth, password=BUONA).json()
    assert r["password_temporanea"] is None and r["invito_inviato"] is False


def test_la_policy_vale_ancora_per_la_password_scritta_dall_admin(client, db, admin, auth, monkeypatch):
    canale(db, monkeypatch)
    assert crea(client, admin, auth, password="debole").status_code == 400


def test_utente_del_dominio_non_riceve_inviti(client, db, admin, auth, monkeypatch):
    inviate = canale(db, monkeypatch)
    r = crea(client, admin, auth, origine_credenziali="dominio").json()
    assert inviate == [] and r["invito_inviato"] is False and r["password_temporanea"] is None


def test_import_csv_manda_il_link_non_la_password(client, db, admin, auth, monkeypatch, crea_ufficio):
    crea_ufficio("Produzione")
    inviate = canale(db, monkeypatch)
    csv_ = b"email,nome,cognome,password,ufficio\nuno@az.it,Uno,U,,Produzione\ndue@az.it,Due,D,Scelta!DaDue12345,Produzione\n"
    r = client.post("/api/auth/users/import-csv", headers=auth(admin), files={"file": ("nuovi.csv", csv_, "text/csv")}).json()
    assert [x["esito"] for x in r["righe"]] == ["creato", "creato"] and [x["password"] for x in r["righe"]] == [None, None]
    assert len(inviate) == 2 and all("reimposta-password?token=" in m[2] for m in inviate)
    assert not any("Scelta!DaDue12345" in m[2] for m in inviate)


def test_import_csv_senza_email_mostra_le_password(client, db, admin, auth, monkeypatch, crea_ufficio):
    crea_ufficio("Produzione")
    canale(db, monkeypatch, attivo=False)
    r = client.post("/api/auth/users/import-csv", headers=auth(admin),
                    files={"file": ("nuovi.csv", b"email,nome,cognome,ufficio\nuno@az.it,Uno,U,Produzione\n", "text/csv")}).json()
    password = r["righe"][0]["password"]
    assert password and client.post("/api/auth/login", json={"email": "uno@az.it", "password": password}).status_code == 200
