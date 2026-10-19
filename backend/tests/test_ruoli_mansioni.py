"""2.2.0: permessi e qualifica sull'utente, un solo ufficio per persona, mansioni, docenti abilitati."""
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.models.edizione import EdizioneDocente, StatoEdizione
from app.models.group import Group, UserGroup
from app.models.mansione import Mansione, UserMansione
from app.models.organizzazione import Organizzazione
from app.models.percorso import PercorsoAssegnazione, PercorsoFormativo, TriggerAssegnazione
from app.models.user import User
from app.services.impronte import impronta

from conftest import PASSWORD


def nuovo(client, auth, admin, **extra):
    corpo = {"email": "nuovo@test.it", "full_name": "Nuovo", "password": PASSWORD, **extra}
    return client.post("/api/auth/users", headers=auth(admin), json=corpo)


@pytest.fixture
def org(db):
    o = Organizzazione(ragione_sociale="Formazione Esterna Srl")
    db.add(o); db.commit(); db.refresh(o)
    return o


# --- chi e' chi -----------------------------------------------------------------------------------

def test_un_interno_ha_un_ufficio_obbligatorio_salvo_l_admin(client, auth, admin, crea_ufficio):
    r = nuovo(client, auth, admin)
    assert r.status_code == 400 and "ufficio" in r.json()["detail"]
    ok = nuovo(client, auth, admin, ufficio_id=str(crea_ufficio("Produzione").id))
    assert ok.status_code == 200 and ok.json()["ufficio"]["name"] == "Produzione"
    assert nuovo(client, auth, admin, email="adm@test.it", is_admin=True).status_code == 200   # l'Admin puo' non averlo


def test_un_esterno_e_un_docente_senza_permessi_ufficio_o_mansioni(client, auth, admin, crea_ufficio, org):
    base = {"is_external": True, "organizzazione_id": str(org.id)}
    assert nuovo(client, auth, admin, **base, is_admin=True).status_code == 400
    assert nuovo(client, auth, admin, **base, is_formazione=True).status_code == 400
    assert nuovo(client, auth, admin, **base, ufficio_id=str(crea_ufficio().id)).status_code == 400
    assert nuovo(client, auth, admin, is_external=True).status_code == 400            # manca l'organizzazione
    r = nuovo(client, auth, admin, **base)
    assert r.status_code == 200 and r.json()["is_formatore"] is True and r.json()["ufficio"] is None


def test_solo_l_admin_assegna_i_permessi(client, auth, formazione, utente):
    assert client.put(f"/api/auth/users/{utente.id}", headers=auth(formazione), json={"is_formazione": True}).status_code == 403
    assert client.put(f"/api/auth/users/{utente.id}", headers=auth(utente), json={"is_admin": True}).status_code == 403


def test_i_permessi_si_sommano_e_senza_permessi_si_e_utenti_semplici(client, auth, admin, db, crea_utente, crea_ufficio):
    u = crea_utente("p@test.it")
    uff = str(crea_ufficio().id)
    r = client.put(f"/api/auth/users/{u.id}", headers=auth(admin), json={"is_formazione": True, "is_formatore": True, "ufficio_id": uff})
    assert r.status_code == 200
    j = r.json()
    assert (j["is_admin"], j["is_formazione"], j["is_formatore"], j["poteri_formazione"]) == (False, True, True, True)
    r = client.put(f"/api/auth/users/{u.id}", headers=auth(admin), json={"is_formazione": False, "is_formatore": False})
    assert r.json()["poteri_formazione"] is False


def test_chi_ha_formazione_ha_i_poteri_ma_non_la_configurazione(client, auth, db, crea_utente, utente):
    f = crea_utente("f@test.it", is_formazione=True)
    assert client.get("/api/corsi", headers=auth(f)).status_code == 200
    assert client.post("/api/groups", headers=auth(f), json={"name": "X"}).status_code == 403     # solo Admin
    assert client.post("/api/mansioni", headers=auth(f), json={"name": "X"}).status_code == 403


def test_un_utente_senza_ufficio_creato_dall_accesso_aziendale_si_disabilita_senza_obblighi(client, auth, admin, crea_utente):
    u = crea_utente("sso@test.it", origine_credenziali="dominio")        # nessun ufficio
    r = client.put(f"/api/auth/users/{u.id}", headers=auth(admin), json={"is_active": False})
    assert r.status_code == 200
    r = client.put(f"/api/auth/users/{u.id}", headers=auth(admin), json={"is_formatore": True})
    assert r.status_code == 200 and r.json()["is_formatore"] is True


# --- un solo ufficio -----------------------------------------------------------------------------

def test_cambiare_ufficio_sposta_la_persona(client, auth, admin, db, crea_utente, crea_ufficio):
    a, b = crea_ufficio("A"), crea_ufficio("B")
    u = crea_utente("u1@test.it")
    client.put(f"/api/auth/users/{u.id}", headers=auth(admin), json={"ufficio_id": str(a.id)})
    r = client.put(f"/api/auth/users/{u.id}", headers=auth(admin), json={"ufficio_id": str(b.id)})
    assert r.json()["ufficio"]["name"] == "B"
    assert db.query(UserGroup).filter(UserGroup.user_id == u.id).count() == 1


def test_il_database_rifiuta_un_secondo_ufficio(db, crea_utente, crea_ufficio):
    u = crea_utente("u2@test.it")
    db.add(UserGroup(user_id=u.id, group_id=crea_ufficio("A").id)); db.commit()
    db.add(UserGroup(user_id=u.id, group_id=crea_ufficio("B").id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_non_si_elimina_un_ufficio_con_persone(client, auth, admin, crea_utente, crea_ufficio):
    g = crea_ufficio("Con persone", membri=[crea_utente("m@test.it")])
    r = client.delete(f"/api/groups/{g.id}", headers=auth(admin))
    assert r.status_code == 400 and "persone" in r.json()["detail"]
    vuoto = crea_ufficio("Vuoto")
    assert client.delete(f"/api/groups/{vuoto.id}", headers=auth(admin)).status_code == 200


# --- docenti -------------------------------------------------------------------------------------

def test_come_docente_si_assegnano_solo_formatori_ed_esterni(client, auth, admin, db, crea_utente, crea_corso, crea_edizione, org):
    ed = crea_edizione(crea_corso())
    semplice = crea_utente("s@test.it")
    formatore = crea_utente("fo@test.it", is_formatore=True)
    esterno = crea_utente("es@test.it", is_external=True, organizzazione_id=org.id)
    r = client.post(f"/api/edizioni/{ed.id}/docenti", headers=auth(admin), json={"user_id": str(semplice.id)})
    assert r.status_code == 400 and "Formatore" in r.json()["detail"]
    assert client.post(f"/api/edizioni/{ed.id}/docenti", headers=auth(admin), json={"user_id": str(formatore.id)}).status_code == 200
    assert client.post(f"/api/edizioni/{ed.id}/docenti", headers=auth(admin), json={"user_id": str(esterno.id)}).status_code == 200
    assert db.query(EdizioneDocente).filter(EdizioneDocente.edizione_id == ed.id).count() == 2


def test_l_elenco_dei_possibili_docenti(client, auth, admin, crea_utente, org):
    crea_utente("s@test.it"); crea_utente("fo@test.it", is_formatore=True)
    crea_utente("es@test.it", is_external=True, organizzazione_id=org.id)
    tutti = {u["email"] for u in client.get("/api/auth/users/simple", headers=auth(admin)).json()}
    docenti = {u["email"] for u in client.get("/api/auth/users/simple?formatori=true", headers=auth(admin)).json()}
    assert {"s@test.it", "fo@test.it", "es@test.it"} <= tutti
    assert docenti == {"fo@test.it", "es@test.it"}


# --- mansioni ------------------------------------------------------------------------------------

def test_mansioni_si_creano_si_cambiano_e_non_si_ripetono(client, auth, admin, utente):
    r = client.post("/api/mansioni", headers=auth(admin), json={"name": "Preposto"})
    assert r.status_code == 200
    mid = r.json()["id"]
    assert client.post("/api/mansioni", headers=auth(admin), json={"name": "preposto"}).status_code == 400      # senza badare alle maiuscole
    assert client.put(f"/api/mansioni/{mid}", headers=auth(admin), json={"name": "Preposto sicurezza", "is_active": False}).json()["is_active"] is False
    assert client.post("/api/mansioni", headers=auth(utente), json={"name": "X"}).status_code == 403
    assert [m["name"] for m in client.get("/api/mansioni", headers=auth(utente)).json()] == ["Preposto sicurezza"]   # tutti la leggono


def test_una_persona_puo_avere_piu_mansioni_e_si_vedono_nell_elenco(client, auth, admin, db, crea_utente):
    u = crea_utente("m1@test.it")
    ids = [client.post("/api/mansioni", headers=auth(admin), json={"name": n}).json()["id"] for n in ("Preposto", "Antincendio")]
    r = client.put(f"/api/auth/users/{u.id}", headers=auth(admin), json={"mansione_ids": ids})
    assert r.status_code == 200 and [m["name"] for m in r.json()["mansioni"]] == ["Antincendio", "Preposto"]
    elenco = {x["email"]: x for x in client.get("/api/auth/users", headers=auth(admin)).json()}
    assert len(elenco["m1@test.it"]["mansioni"]) == 2
    assert client.get("/api/mansioni", headers=auth(admin)).json()[0]["persone"] == 1
    r = client.put(f"/api/auth/users/{u.id}", headers=auth(admin), json={"mansione_ids": [ids[0], "00000000-0000-0000-0000-000000000000"]})
    assert r.status_code == 400


def test_eliminare_una_mansione_la_toglie_alle_persone_ma_non_se_un_percorso_la_usa(client, auth, admin, db, crea_utente):
    u = crea_utente("m2@test.it")
    mid = client.post("/api/mansioni", headers=auth(admin), json={"name": "Carrellista"}).json()["id"]
    client.put(f"/api/auth/users/{u.id}", headers=auth(admin), json={"mansione_ids": [mid]})
    p = PercorsoFormativo(nome="Carrelli", trigger_tipo=TriggerAssegnazione.mansione, trigger_mansione_id=mid)
    db.add(p); db.commit()
    assert client.delete(f"/api/mansioni/{mid}", headers=auth(admin)).status_code == 400
    p.trigger_tipo, p.trigger_mansione_id = TriggerAssegnazione.manuale, None
    db.commit()
    assert client.delete(f"/api/mansioni/{mid}", headers=auth(admin)).status_code == 200
    assert db.query(UserMansione).count() == 0


def test_un_percorso_per_mansione_si_assegna_a_chi_la_ha(client, auth, admin, db, crea_utente):
    con, senza = crea_utente("con@test.it"), crea_utente("senza@test.it")
    mid = client.post("/api/mansioni", headers=auth(admin), json={"name": "Preposto"}).json()["id"]
    r = client.post("/api/percorsi", headers=auth(admin), json={"nome": "Preposti", "trigger_tipo": "mansione", "trigger_mansione_id": mid, "steps": []})
    assert r.status_code == 200 and r.json()["trigger_mansione_id"] == mid
    client.put(f"/api/auth/users/{con.id}", headers=auth(admin), json={"mansione_ids": [mid]})   # assegnare la mansione fa partire il percorso
    chi = {str(a.user_id) for a in db.query(PercorsoAssegnazione).all()}
    assert chi == {str(con.id)} and str(senza.id) not in chi


# --- importazione CSV ----------------------------------------------------------------------------

def csv(client, auth, admin, testo):
    return client.post("/api/auth/users/import-csv", headers=auth(admin), files={"file": ("u.csv", testo, "text/csv")})


def test_csv_con_ufficio_mansioni_e_permessi(client, auth, admin, db, crea_ufficio):
    padre = crea_ufficio("Produzione")
    figlio = Group(name="Linea 2", parent_id=padre.id, is_ufficio=True)
    db.add(figlio); db.commit()
    client.post("/api/mansioni", headers=auth(admin), json={"name": "Preposto"})
    r = csv(client, auth, admin,
            "email,full_name,ufficio,mansioni,formatore,formazione\n"
            "a@az.it,A,Produzione / Linea 2,Preposto;Inesistente,sì,\n"
            "b@az.it,B,,,,\n"
            "c@az.it,C,Magazzino,,,\n"
            "d@az.it,D,Produzione,,,x\n").json()
    esiti = [x["esito"] for x in r["righe"]]
    assert esiti == ["creato", "errore", "errore", "creato"]
    assert "mansioni non trovate: Inesistente" in r["righe"][0]["messaggio"]
    assert "ufficio mancante" in r["righe"][1]["messaggio"] and "non trovato" in r["righe"][2]["messaggio"]
    a = db.query(User).filter(User.email_idx == impronta("a@az.it")).one()
    d = db.query(User).filter(User.email_idx == impronta("d@az.it")).one()
    assert a.is_formatore and not a.is_formazione and d.is_formazione
    assert db.query(UserGroup).filter(UserGroup.user_id == a.id).one().group_id == figlio.id
    assert db.query(UserMansione).filter(UserMansione.user_id == a.id).count() == 1


def test_csv_con_le_vecchie_colonne_spiega_cosa_fare(client, auth, admin):
    r = csv(client, auth, admin, "email,full_name,role,gruppi\nx@az.it,X,user,Produzione\n")
    assert r.status_code == 400 and "ufficio" in r.json()["detail"]


def test_csv_ufficio_con_lo_stesso_nome_in_due_rami_chiede_il_percorso(client, auth, admin, db, crea_ufficio):
    a, b = crea_ufficio("Nord"), crea_ufficio("Sud")
    db.add_all([Group(name="Vendite", parent_id=a.id, is_ufficio=True), Group(name="Vendite", parent_id=b.id, is_ufficio=True)]); db.commit()
    r = csv(client, auth, admin, "email,full_name,ufficio\nx@az.it,X,Vendite\ny@az.it,Y,Nord / Vendite\n").json()
    assert [x["esito"] for x in r["righe"]] == ["errore", "creato"] and "ambiguo" in r["righe"][0]["messaggio"]


# --- esportazione / importazione della configurazione ----------------------------------------------

def test_la_configurazione_porta_con_se_le_mansioni_e_accetta_i_file_vecchi(client, auth, admin, db):
    client.post("/api/mansioni", headers=auth(admin), json={"name": "Preposto", "description": "d"})
    dati = client.get("/api/admin/configurazione/export", headers=auth(admin)).json()
    assert [m["nome"] for m in dati["mansioni"]] == ["Preposto"] and "permessi" not in (dati["gruppi"][0] if dati["gruppi"] else {})
    vecchio = {"formato": "elearning-configurazione", "schema": 1,
               "gruppi": [{"percorso": "Produzione", "nome": "Produzione", "ufficio": True},
                          {"percorso": "Antincendio", "nome": "Antincendio", "ufficio": False}],
               "percorsi": [{"nome": "Corso fuoco", "motivo": "legge", "trigger": "gruppo", "trigger_gruppo": "Antincendio", "passi": []}]}
    r = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": vecchio, "applica": True})
    assert r.status_code == 200, r.text
    assert db.query(Group).filter(Group.name == "Produzione").one().is_ufficio
    assert db.query(Group).filter(Group.name == "Antincendio").first() is None            # non e' piu' un gruppo
    m = db.query(Mansione).filter(Mansione.name == "Antincendio").one()
    p = db.query(PercorsoFormativo).filter(PercorsoFormativo.nome == "Corso fuoco").one()
    assert p.trigger_tipo == TriggerAssegnazione.mansione and p.trigger_mansione_id == m.id


def test_l_esportazione_degli_utenti_ha_permessi_ufficio_e_mansioni(client, auth, admin, crea_ufficio, crea_utente, db):
    u = crea_utente("e@test.it", is_formazione=True, is_formatore=True, full_name="Elena")
    db.add(UserGroup(user_id=u.id, group_id=crea_ufficio("Produzione").id)); db.commit()
    testo = client.get("/api/auth/users/export?formato=csv", headers=auth(admin)).content.decode("utf-8-sig")
    intestazione = testo.splitlines()[0]
    assert "Permessi" in intestazione and "Ufficio" in intestazione and "Mansioni" in intestazione and "Ruolo" not in intestazione
    riga = [r for r in testo.splitlines() if "e@test.it" in r][0]
    assert "Formazione; Formatore" in riga and "Produzione" in riga


def test_un_esterno_non_si_iscrive_come_discente(client, auth, admin, crea_utente, crea_corso, crea_edizione, org):
    ed = crea_edizione(crea_corso(), stato=StatoEdizione.pianificata)
    esterno = crea_utente("es2@test.it", is_external=True, organizzazione_id=org.id)
    r = client.post(f"/api/edizioni/{ed.id}/iscrizioni", headers=auth(admin), json=[str(esterno.id)])
    assert r.status_code == 200 and r.json()["iscritti"] == []
    assert "docente" in r.json()["non_iscritti"][0]["motivo"]      # la persona e' esclusa, con il motivo
