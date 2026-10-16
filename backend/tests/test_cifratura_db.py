"""Dati personali cifrati nel database (1.9.7): scrittura, lettura, ricerca per impronta, conversione, chiavi."""
import pytest
import sqlalchemy as sa

from app.config import settings
from app.database import engine
from app.models.audit import AuditLog
from app.models.organizzazione import Organizzazione
from app.models.user import User
from app.services import cifratura as c
from app.services import cifratura_ops as ops
from app.services.impronte import impronta

from conftest import PASSWORD


@pytest.fixture
def chiave(monkeypatch):
    k = c.genera_chiave()
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", k)
    monkeypatch.setattr(settings, "CHIAVI_CIFRATURA_PRECEDENTI", None)
    return k


def grezzo(sql, **p):
    """Il valore come e' scritto nel database, senza passare dal tipo cifrato."""
    with engine.connect() as conn:
        return conn.execute(sa.text(sql), p).fetchall()


def test_i_dati_personali_sono_cifrati_nel_database_e_in_chiaro_nel_programma(chiave, db, crea_utente):
    u = crea_utente("mario.rossi@azienda.it", full_name="Mario Rossi")
    riga = grezzo("SELECT email, full_name, email_idx FROM users WHERE id = :i", i=u.id)[0]
    assert riga[0].startswith("enc:v1:") and riga[1].startswith("enc:v1:")
    assert "mario" not in riga[0].lower() and "rossi" not in riga[1].lower() and "mario" not in riga[2]
    db.expire_all()
    letto = db.get(User, u.id)
    assert letto.email == "mario.rossi@azienda.it" and letto.full_name == "Mario Rossi"
    assert riga[2] == impronta("MARIO.ROSSI@azienda.it ")      # senza maiuscole e spazi ai lati


def test_senza_chiave_i_dati_restano_in_chiaro_ma_si_cercano_uguale(db, crea_utente, monkeypatch):
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", None)
    u = crea_utente("a@azienda.it", full_name="Anna")
    assert grezzo("SELECT email FROM users WHERE id = :i", i=u.id)[0][0] == "a@azienda.it"
    assert db.query(User).filter(User.email_idx == impronta("A@azienda.it")).one().id == u.id


def test_login_con_dati_cifrati_e_senza_badare_alle_maiuscole(chiave, client, crea_utente):
    crea_utente("lui@azienda.it", full_name="Lui")
    for scritto in ("lui@azienda.it", "LUI@Azienda.IT"):
        r = client.post("/api/auth/login", json={"email": scritto, "password": PASSWORD})
        assert r.status_code == 200, r.text
    assert client.post("/api/auth/login", json={"email": "lui@azienda.it", "password": "no"}).status_code == 401


def test_due_utenti_con_la_stessa_email_scritta_diversamente_non_si_creano(chiave, client, admin, auth):
    corpo = {"email": "x@azienda.it", "password": PASSWORD, "full_name": "X", "role": "user"}
    assert client.post("/api/auth/users", headers=auth(admin), json=corpo).status_code in (200, 201)
    assert client.post("/api/auth/users", headers=auth(admin), json={**corpo, "email": "X@AZIENDA.IT"}).status_code == 400


def test_elenco_utenti_ordinato_per_nome_nel_programma(chiave, client, admin, auth, crea_utente):
    for n in ("Zeno", "anna", "Mario"):
        crea_utente(f"{n.lower()}@azienda.it", full_name=n)
    nomi = [u["full_name"] for u in client.get("/api/auth/users", headers=auth(admin)).json()]
    assert nomi == sorted(nomi, key=str.casefold)


def test_un_confronto_scritto_per_sbagliato_sulla_colonna_cifrata_da_errore(chiave, db):
    with pytest.raises(TypeError):
        db.query(User).filter(User.email == "x@azienda.it").all()
    with pytest.raises(TypeError):
        db.query(User).filter(User.full_name.ilike("%a%")).all()
    assert db.query(User).filter(User.email.isnot(None)).count() == 0     # il confronto con NULL e' ammesso


def test_registro_attivita_cifra_email_ip_e_dettaglio_e_si_filtra_per_valore_esatto(chiave, client, admin, auth, utente):
    client.post("/api/auth/login", json={"email": utente.email, "password": PASSWORD}, headers={"X-Real-IP": "198.51.100.7"})
    riga = grezzo("SELECT user_email, ip_address, detail FROM audit_log WHERE action = 'LOGIN'")[0]
    assert riga[0].startswith("enc:v1:") and riga[1].startswith("enc:v1:") and riga[2].startswith("enc:v1:")
    voci = lambda **p: client.get("/api/admin/audit", headers=auth(admin), params={"livello": "tutti", **p}).json()
    assert voci(ip="198.51.100.7")["totale"] == 1 and voci(ip="198.51.100.")["totale"] == 0
    elemento = voci(action="LOGIN")["items"][0]
    assert elemento["user_email"] == utente.email and elemento["ip_address"] == "198.51.100.7"
    assert "utente@test.it" in elemento["detail"]          # per gli eventi sugli utenti il nome sta nel dettaglio cifrato


def test_l_entita_utente_non_lascia_l_email_in_chiaro(chiave, client, utente):
    client.post("/api/auth/login", json={"email": utente.email, "password": PASSWORD})
    assert grezzo("SELECT entity_name FROM audit_log WHERE action = 'LOGIN'")[0][0] is None
    assert not [r for r in grezzo("SELECT entity_name FROM audit_log") if r[0] and "@" in r[0]]


def test_enti_esterni_cifrati(chiave, db):
    o = Organizzazione(ragione_sociale="Ente SRL", referente="Luca Bianchi", email="luca@ente.it", telefono="333 1234567")
    db.add(o)
    db.commit()
    riga = grezzo("SELECT ragione_sociale, referente, email, telefono FROM organizzazioni")[0]
    assert riga[0] == "Ente SRL" and all(v.startswith("enc:v1:") for v in riga[1:])
    db.expire_all()
    assert db.get(Organizzazione, o.id).telefono == "333 1234567"


# --- conversione dei dati esistenti ------------------------------------------------------------------------

def test_cifra_decifra_e_ruota_i_dati_gia_presenti(db, crea_utente, monkeypatch):
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", None)
    u = crea_utente("vecchio@azienda.it", full_name="Vecchio Utente")
    db.add(AuditLog(action="PROVA", user_email="vecchio@azienda.it", ip_address="203.0.113.5", detail="dettaglio"))
    db.commit()
    assert ops.riepilogo_dati_personali(db)["cifrato"] == 0 and ops.riepilogo_dati_personali(db)["chiaro"] == 5   # nome ed email dell'utente, email IP e dettaglio del registro

    prima = c.genera_chiave()
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", prima)
    ops.converti_db(db, "cifra")
    assert ops.riepilogo_dati_personali(db)["chiaro"] == 0
    assert grezzo("SELECT email FROM users WHERE id = :i", i=u.id)[0][0].startswith("enc:v1:")
    db.expire_all()
    assert db.get(User, u.id).full_name == "Vecchio Utente"

    # cambio chiave: la vecchia resta tra le precedenti, 'ruota' ricifra con la nuova; le impronte non cambiano
    impronta_prima = grezzo("SELECT email_idx FROM users WHERE id = :i", i=u.id)[0][0]
    nuova = c.genera_chiave()
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", nuova)
    monkeypatch.setattr(settings, "CHIAVI_CIFRATURA_PRECEDENTI", prima)
    db.expire_all()
    assert db.get(User, u.id).email == "vecchio@azienda.it"     # letto con la chiave precedente
    ops.converti_db(db, "ruota")
    monkeypatch.setattr(settings, "CHIAVI_CIFRATURA_PRECEDENTI", None)
    db.expire_all()
    assert db.get(User, u.id).email == "vecchio@azienda.it"     # ora basta la chiave nuova
    assert grezzo("SELECT email_idx FROM users WHERE id = :i", i=u.id)[0][0] == impronta_prima

    ops.converti_db(db, "decifra")
    assert grezzo("SELECT email, full_name FROM users WHERE id = :i", i=u.id)[0] == ("vecchio@azienda.it", "Vecchio Utente")
    assert ops.riepilogo_dati_personali(db)["cifrato"] == 0


def test_disattiva_si_rifiuta_se_restano_dati_personali_cifrati(chiave, db, crea_utente, tmp_path, monkeypatch):
    monkeypatch.setattr(ops, "CARTELLE", [str(tmp_path)])
    crea_utente("a@azienda.it", full_name="A")
    ops.controlla_avvio(db)
    with pytest.raises(ops.ErroreAvvio):
        ops.disattiva(db)
    ops.converti_db(db, "decifra")
    assert "disattivata" in ops.disattiva(db)


def test_la_pagina_stato_conta_i_dati_personali(client, db, admin, auth, monkeypatch):
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", None)
    d = client.get("/api/admin/salute", headers=auth(admin)).json()["cifratura"]["dati_personali"]
    assert d["cifrato"] == 0 and d["chiaro"] >= 2                 # nome ed email dell'amministratore
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", c.genera_chiave())
    ops.converti_db(db, "cifra")
    d = client.get("/api/admin/salute", headers=auth(admin)).json()["cifratura"]["dati_personali"]
    assert d["chiaro"] == 0 and d["cifrato"] >= 2


def test_lo_strumento_conta_tutto_il_registro_la_pagina_solo_le_ultime_righe(db, monkeypatch):
    monkeypatch.setattr(settings, "CHIAVE_CIFRATURA", None)
    monkeypatch.setattr(ops, "COLONNE_PERSONALI", {"audit_log": ("user_email",)})
    for n in range(3):
        db.add(AuditLog(action="PROVA", user_email=f"{n}@azienda.it"))
    db.commit()
    assert ops.stato(db, completo=True)["dati_personali"]["chiaro"] == 3
    assert ops.stato(db)["dati_personali"]["chiaro"] == 3          # sotto il limite coincidono
    monkeypatch.setattr(ops, "RIGHE_REGISTRO_NELLO_STATO", 2)
    assert ops.stato(db)["dati_personali"]["chiaro"] == 2          # la pagina guarda solo le ultime righe
    assert ops.stato(db, completo=True)["dati_personali"]["chiaro"] == 3
