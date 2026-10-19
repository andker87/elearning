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
from app.services import entra_sync as entra
from app.services.impronte import impronta

from conftest import PASSWORD


def nuovo(client, auth, admin, **extra):
    corpo = {"email": "nuovo@test.it", "nome": "Nuovo", "cognome": "Utente", "password": PASSWORD, **extra}
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
    assert r.status_code == 400 and "Docente" in r.json()["detail"]
    assert client.post(f"/api/edizioni/{ed.id}/docenti", headers=auth(admin), json={"user_id": str(formatore.id)}).status_code == 200
    assert client.post(f"/api/edizioni/{ed.id}/docenti", headers=auth(admin), json={"user_id": str(esterno.id)}).status_code == 200
    assert db.query(EdizioneDocente).filter(EdizioneDocente.edizione_id == ed.id).count() == 2


def test_l_elenco_dei_possibili_docenti(client, auth, admin, crea_utente, org):
    crea_utente("s@test.it"); crea_utente("fo@test.it", is_formatore=True)
    crea_utente("es@test.it", is_external=True, organizzazione_id=org.id)
    tutti = {u["email"] for u in client.get("/api/auth/users/simple", headers=auth(admin)).json()}
    docenti = {u["email"] for u in client.get("/api/auth/users/simple?docenti=true", headers=auth(admin)).json()}
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
            "email,nome,cognome,ufficio,mansioni,docente,formazione\n"
            "a@az.it,A,A,Produzione / Linea 2,Preposto;Inesistente,sì,\n"
            "b@az.it,B,B,,,,\n"
            "c@az.it,C,C,Magazzino,,,\n"
            "d@az.it,D,D,Produzione,,,x\n").json()
    esiti = [x["esito"] for x in r["righe"]]
    assert esiti == ["creato", "creato", "creato", "creato"]                  # un ufficio o una mansione che non c'e' non scarta la riga
    assert r["con_avvisi"] == 3 and r["errori"] == 0
    assert "mansione «Inesistente» non presente" in r["righe"][0]["avvisi"][0]
    assert "ufficio non indicato" in r["righe"][1]["avvisi"][0] and "«Magazzino» non presente" in r["righe"][2]["avvisi"][0]
    assert r["righe"][3]["avvisi"] == []
    senza = [db.query(User).filter(User.email_idx == impronta(e)).one() for e in ("b@az.it", "c@az.it")]
    assert all(db.query(UserGroup).filter(UserGroup.user_id == u.id).count() == 0 for u in senza)     # create senza ufficio
    a = db.query(User).filter(User.email_idx == impronta("a@az.it")).one()
    d = db.query(User).filter(User.email_idx == impronta("d@az.it")).one()
    assert a.is_formatore and not a.is_formazione and d.is_formazione
    assert db.query(UserGroup).filter(UserGroup.user_id == a.id).one().group_id == figlio.id
    assert db.query(UserMansione).filter(UserMansione.user_id == a.id).count() == 1


def test_csv_con_le_vecchie_colonne_spiega_cosa_fare(client, auth, admin):
    r = csv(client, auth, admin, "email,nome,cognome,role,gruppi\nx@az.it,X,Y,user,Produzione\n")
    assert r.status_code == 400 and "ufficio" in r.json()["detail"]


def test_csv_ufficio_con_lo_stesso_nome_in_due_rami_chiede_il_percorso(client, auth, admin, db, crea_ufficio):
    a, b = crea_ufficio("Nord"), crea_ufficio("Sud")
    db.add_all([Group(name="Vendite", parent_id=a.id, is_ufficio=True), Group(name="Vendite", parent_id=b.id, is_ufficio=True)]); db.commit()
    r = csv(client, auth, admin, "email,nome,cognome,ufficio\nx@az.it,X,X,Vendite\ny@az.it,Y,Y,Nord / Vendite\n").json()
    assert [x["esito"] for x in r["righe"]] == ["creato", "creato"] and "ambiguo" in r["righe"][0]["avvisi"][0] and r["righe"][1]["avvisi"] == []


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
    assert "Ruoli" in intestazione and "Permessi" not in intestazione and "Ufficio" in intestazione and "Mansioni" in intestazione and "Ruolo" not in intestazione
    riga = [r for r in testo.splitlines() if "e@test.it" in r][0]
    assert "Formazione; Docente" in riga and "Produzione" in riga


def test_un_esterno_non_si_iscrive_come_discente(client, auth, admin, crea_utente, crea_corso, crea_edizione, org):
    ed = crea_edizione(crea_corso(), stato=StatoEdizione.pianificata)
    esterno = crea_utente("es2@test.it", is_external=True, organizzazione_id=org.id)
    r = client.post(f"/api/edizioni/{ed.id}/iscrizioni", headers=auth(admin), json=[str(esterno.id)])
    assert r.status_code == 200 and r.json()["iscritti"] == []
    assert "docente" in r.json()["non_iscritti"][0]["motivo"]      # la persona e' esclusa, con il motivo


def test_i_modelli_csv_scaricabili_si_importano_cosi_come_sono(client, auth, admin, db, crea_ufficio):
    """Stesso contenuto dei modelli che la pagina Utenti fa scaricare (separatore «;», BOM, riga di esempio)."""
    crea_ufficio("Alfa")
    client.post("/api/mansioni", headers=auth(admin), json={"name": "Preposto"})
    nuovi = "﻿email;nome;cognome;ufficio;mansioni;admin;formazione;docente;is_external;organizzazione;data_ingresso;password\r\n" \
            "mario.rossi@azienda.it;Mario;Rossi;Alfa;Preposto;no;no;no;no;;2026-01-15;\r\n"
    r = csv(client, auth, admin, nuovi.encode("utf-8")).json()
    assert [x["esito"] for x in r["righe"]] == ["creato"], r
    u = db.query(User).filter(User.email_idx == impronta("mario.rossi@azienda.it")).one()
    assert (u.nome, u.cognome) == ("Mario", "Rossi") and not u.is_admin and not u.is_formatore and u.data_ingresso is not None
    cessati = "﻿email\r\nmario.rossi@azienda.it\r\n"
    r = client.post("/api/auth/users/import-csv?modo=cessati", headers=auth(admin), files={"file": ("modello-cessati.csv", cessati.encode("utf-8"), "text/csv")}).json()
    assert [x["esito"] for x in r["righe"]] == ["disattivato"]


# --- correzioni dalla review ----------------------------------------------------------------------

def test_csv_l_invito_parte_con_il_nome_della_persona_non_con_una_mansione(client, auth, admin, db, crea_ufficio, monkeypatch):
    from test_inviti import canale
    inviate = canale(db, monkeypatch)
    crea_ufficio("Produzione")
    client.post("/api/mansioni", headers=auth(admin), json={"name": "Preposto"})
    r = csv(client, auth, admin, "email,nome,cognome,ufficio,mansioni\nmario@az.it,Mario,Rossi,Produzione,Preposto;\n").json()
    assert [x["esito"] for x in r["righe"]] == ["creato"]
    assert len(inviate) == 1 and "Ciao Mario Rossi," in inviate[0][2] and "Preposto" not in inviate[0][2]


def test_entra_non_annulla_una_correzione_fatta_a_mano_quando_c_e_solo_il_nome_visualizzato(db, crea_utente):
    crea_utente("a@az.it", nome="Maria Grazia", cognome="Rossi")        # divisa a mano: il nome intero non e' cambiato
    membro = {"email": "a@az.it", "indirizzi": ["a@az.it"], "nome": "Maria Grazia Rossi", "given": "", "cognome": "", "attivo": True, "assunto_il": None}
    assert entra.calcola_piano(db, [membro])["aggiorna"] == []
    membro["nome"] = "Maria Grazia Bianchi"                             # cambiato davvero in Entra: si aggiorna (con la divisione semplice)
    piano = entra.calcola_piano(db, [membro])
    assert [x["email"] for x in piano["aggiorna"]] == ["a@az.it"] and piano["aggiorna"][0]["a"] == "Maria Grazia Bianchi"


def test_non_si_elimina_un_ufficio_usato_da_un_percorso(client, auth, admin, db, crea_ufficio):
    g = crea_ufficio("Usato")
    p = PercorsoFormativo(nome="Per ufficio", trigger_tipo=TriggerAssegnazione.gruppo, trigger_gruppo_id=g.id)
    db.add(p); db.commit()
    r = client.delete(f"/api/groups/{g.id}", headers=auth(admin))
    assert r.status_code == 400 and "percorso" in r.json()["detail"]
    p.trigger_tipo, p.trigger_gruppo_id = TriggerAssegnazione.manuale, None
    db.commit()
    assert client.delete(f"/api/groups/{g.id}", headers=auth(admin)).status_code == 200


def test_un_file_vecchio_con_un_gruppo_che_ora_e_un_ufficio_omonimo_avvisa(client, auth, admin, crea_ufficio):
    crea_ufficio("Antincendio")                                          # qui esiste un ufficio con lo stesso nome del vecchio gruppo
    vecchio = {"formato": "elearning-configurazione", "schema": 1,
               "gruppi": [{"percorso": "Antincendio", "nome": "Antincendio", "ufficio": False}],
               "percorsi": [{"nome": "Corso fuoco", "motivo": "legge", "trigger": "gruppo", "trigger_gruppo": "Antincendio", "passi": []}]}
    r = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": vecchio, "applica": False})
    assert r.status_code == 200
    assert any("stesso nome" in a for a in r.json()["avvisi"]), r.json()["avvisi"]


def test_il_testo_dei_ruoli_nell_esportazione(db, crea_utente, org):
    from app.services.persone import permessi_testo
    assert permessi_testo(crea_utente("u1@t.it")) == "Utente"
    assert permessi_testo(crea_utente("u2@t.it", is_admin=True, is_formatore=True)) == "Admin; Docente"
    assert permessi_testo(crea_utente("u3@t.it", is_external=True, organizzazione_id=org.id)) == "Docente; Esterno"
