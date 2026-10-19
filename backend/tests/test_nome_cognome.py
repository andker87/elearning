"""2.3.0: nome e cognome separati."""
import sqlalchemy as sa

from app.config import settings
from app.database import engine
from app.models.user import User
from app.services import cifratura as c
from app.services import entra_sync as entra
from app.services.impronte import impronta
from app.services.persone import dividi_nome

from conftest import PASSWORD


def test_dividi_nome():
    assert dividi_nome("Mario Rossi") == ("Mario", "Rossi")
    assert dividi_nome("  Maria   Grazia Rossi ") == ("Maria", "Grazia Rossi")      # la prima parola e' il nome, il resto il cognome
    assert dividi_nome("Cher") == ("Cher", "")
    assert dividi_nome("") == ("", "") and dividi_nome(None) == ("", "")


def test_il_nome_intero_resta_disponibile_per_chi_lo_mostra(db, crea_utente):
    u = crea_utente("a@test.it", nome="Anna", cognome="De Luca")
    assert (u.nome, u.cognome, u.full_name) == ("Anna", "De Luca", "Anna De Luca")
    v = crea_utente("b@test.it", full_name="Luca Verdi")                        # scrivere il nome intero lo divide
    assert (v.nome, v.cognome) == ("Luca", "Verdi")


def test_creare_e_modificare_con_nome_e_cognome(client, auth, admin, crea_ufficio):
    corpo = {"email": "n@test.it", "password": PASSWORD, "ufficio_id": str(crea_ufficio().id)}
    assert client.post("/api/auth/users", headers=auth(admin), json={**corpo, "nome": "Anna"}).status_code == 422          # il cognome serve
    r = client.post("/api/auth/users", headers=auth(admin), json={**corpo, "nome": " Anna ", "cognome": " Bianchi "})
    assert r.status_code == 200
    j = r.json()
    assert (j["nome"], j["cognome"], j["full_name"]) == ("Anna", "Bianchi", "Anna Bianchi")
    r = client.put(f"/api/auth/users/{j['id']}", headers=auth(admin), json={"cognome": "Rossi"})
    assert (r.json()["nome"], r.json()["cognome"]) == ("Anna", "Rossi")
    assert client.put(f"/api/auth/users/{j['id']}", headers=auth(admin), json={"nome": "  "}).status_code == 400


def test_gli_elenchi_sono_in_ordine_di_cognome_poi_nome(client, auth, admin, crea_utente):
    crea_utente("1@t.it", nome="Zoe", cognome="Alfa"); crea_utente("2@t.it", nome="Anna", cognome="Zeta")
    crea_utente("3@t.it", nome="Bruno", cognome="alfa"); crea_utente("4@t.it", nome="Carla", cognome="Medi")
    ordine = [u["full_name"] for u in client.get("/api/auth/users", headers=auth(admin)).json() if u["email"] != "admin@test.it"]
    assert ordine == ["Bruno alfa", "Zoe Alfa", "Carla Medi", "Anna Zeta"]      # senza badare alle maiuscole; a parita' di cognome, il nome


def test_csv_con_nome_e_cognome(client, auth, admin, db, crea_ufficio):
    crea_ufficio("Produzione")
    f = lambda t: client.post("/api/auth/users/import-csv", headers=auth(admin), files={"file": ("u.csv", t, "text/csv")})
    r = f("email,nome,cognome,ufficio\na@az.it,Anna,De Luca,Produzione\nb@az.it,Bruno,,Produzione\n").json()
    assert [x["esito"] for x in r["righe"]] == ["creato", "errore"] and "cognome mancante" in r["righe"][1]["messaggio"]
    a = db.query(User).filter(User.email_idx == impronta("a@az.it")).one()
    assert (a.nome, a.cognome) == ("Anna", "De Luca")
    vecchio = f("email,full_name,ufficio\nx@az.it,X Y,Produzione\n")
    assert vecchio.status_code == 400 and "nome" in vecchio.json()["detail"] and "cognome" in vecchio.json()["detail"]


def test_la_configurazione_iniziale_chiede_nome_e_cognome(client, db):
    assert client.post("/api/setup/init", json={"nome": "Anna", "email": "a@x.it", "password": PASSWORD}).status_code == 422
    r = client.post("/api/setup/init", json={"nome": "Anna", "cognome": "Bianchi", "email": "a@x.it", "password": PASSWORD})
    assert r.status_code == 200
    u = db.query(User).filter(User.email_idx == impronta("a@x.it")).one()
    assert (u.nome, u.cognome, u.is_admin) == ("Anna", "Bianchi", True)


def test_nome_e_cognome_sono_cifrati_nel_database(db, crea_utente, monkeypatch):
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", c.genera_chiave())
    u = crea_utente("x@test.it", nome="Mario", cognome="Rossi")
    with engine.connect() as conn:
        n, cg = conn.execute(sa.text("SELECT nome, cognome FROM users WHERE id = :i"), {"i": u.id}).one()
    assert n.startswith("enc:v1:") and cg.startswith("enc:v1:") and "rossi" not in cg.lower()


# --- accesso aziendale ed Entra ---------------------------------------------------------------------

def test_entra_usa_nome_e_cognome_di_entra_quando_ci_sono_altrimenti_divide_il_nome(db):
    membri = [{"email": "a@az.it", "indirizzi": ["a@az.it"], "nome": "Anna Maria De Luca", "given": "Anna Maria", "cognome": "De Luca",
               "attivo": True, "assunto_il": None},
              {"email": "b@az.it", "indirizzi": ["b@az.it"], "nome": "Bruno Verdi", "given": "", "cognome": "",
               "attivo": True, "assunto_il": None}]
    piano = entra.calcola_piano(db, membri)
    entra.applica_piano(db, piano)
    db.commit()
    a = db.query(User).filter(User.email_idx == impronta("a@az.it")).one()
    b = db.query(User).filter(User.email_idx == impronta("b@az.it")).one()
    assert (a.nome, a.cognome) == ("Anna Maria", "De Luca")        # dai dati di Entra, senza indovinare
    assert (b.nome, b.cognome) == ("Bruno", "Verdi")               # nome intero diviso
    # un cambio di cognome in Entra aggiorna la persona
    membri[0]["cognome"] = "Bianchi"
    piano = entra.calcola_piano(db, membri)
    assert [x["email"] for x in piano["aggiorna"]] == ["a@az.it"] and piano["aggiorna"][0]["a"] == "Anna Maria Bianchi"
    entra.applica_piano(db, piano); db.commit(); db.expire_all()
    assert db.query(User).filter(User.email_idx == impronta("a@az.it")).one().cognome == "Bianchi"
