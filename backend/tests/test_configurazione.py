"""Esportazione e importazione della configurazione."""
import json

from app.models.azienda import Azienda
from app.models.audit import AuditLog
from app.models.corso import Corso
from app.models.group import Group
from app.models.organizzazione import Organizzazione
from app.models.percorso import PercorsoFormativo, PercorsoStep, PercorsoStepPrerequisito
from app.models.user import User


def configura(db, crea_utente, crea_corso, crea_ufficio, crea_percorso):
    db.add(Azienda(ragione_sociale="Acme Spa", partita_iva="01234567890", nome_piattaforma="Formazione Acme", url_pubblico="https://f.acme.it",
                   privacy_testo="Titolare: Acme", vapid_private_key="SEGRETISSIMA", vapid_public_key="pubblica"))
    db.add(Organizzazione(ragione_sociale="Ente Alfa", tipo="ente accreditato", referente="Mario"))
    resp = crea_utente("resp@acme.it")
    direzione = crea_ufficio("Direzione", responsabile=resp)
    legale = crea_ufficio("Legale")
    legale.parent_id = direzione.id
    db.commit()
    c1 = crea_corso("Privacy", validita_mesi=24, rinnovo_automatico=True, rinnovo_giorni_anticipo=45, categoria="compliance")
    c2 = crea_corso("Antiriciclaggio", ha_test_finale=True)
    p = crea_percorso([c1, c2], [], nome="Onboarding")
    p.trigger_tipo = "gruppo"
    p.trigger_gruppo_id = legale.id
    s1, s2 = sorted(p.steps, key=lambda s: s.ordine)
    db.add(PercorsoStepPrerequisito(step_id=s2.id, richiede_step_id=s1.id))
    db.commit()


def cancella_configurazione(db):
    from sqlalchemy import text
    for t in ("percorso_step_prerequisiti", "percorso_steps", "percorso_assegnazioni", "percorsi_formativi", "corsi", "organizzazioni", "user_groups"):
        db.execute(text(f"DELETE FROM {t}"))
    db.execute(text("UPDATE groups SET parent_id = NULL"))
    db.execute(text("DELETE FROM groups"))
    db.commit()


def test_il_file_non_contiene_segreti_ne_cio_che_e_fuori_ambito(client, db, admin, auth, crea_utente, crea_corso, crea_ufficio, crea_percorso):
    configura(db, crea_utente, crea_corso, crea_ufficio, crea_percorso)
    r = client.get("/api/admin/configurazione/export", headers=auth(admin))
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"] and r.headers["content-disposition"].endswith('.json"')
    for vietato in ("SEGRETISSIMA", "vapid", "hashed_password", "calendar_token", "sso_subject"):
        assert vietato not in r.text
    dati = r.json()
    assert dati["formato"] == "elearning-configurazione" and dati["schema"] == 1 and dati["non_incluso"]
    assert dati["azienda"]["nome_piattaforma"] == "Formazione Acme" and dati["azienda"]["privacy_testo"] == "Titolare: Acme"
    assert {g["percorso"] for g in dati["gruppi"]} == {"Direzione", "Direzione / Legale"}
    assert next(g for g in dati["gruppi"] if g["nome"] == "Direzione")["responsabile"] == "resp@acme.it"
    assert {c["titolo"] for c in dati["corsi"]} == {"Privacy", "Antiriciclaggio"}
    onb = dati["percorsi"][0]
    assert onb["trigger_gruppo"] == "Direzione / Legale" and [p["corso"] for p in onb["passi"]] == ["Privacy", "Antiriciclaggio"]
    assert onb["passi"][1]["richiede"] == ["Privacy"]
    assert db.query(AuditLog).filter(AuditLog.action == "CONFIG_EXPORT").count() == 1


def test_solo_l_admin_tecnico(client, formazione, utente, auth):
    for persona in (formazione, utente):
        assert client.get("/api/admin/configurazione/export", headers=auth(persona)).status_code == 403
        assert client.post("/api/admin/configurazione/import", headers=auth(persona), json={"contenuto": {}}).status_code == 403


def test_ricostruzione_in_un_ambiente_vuoto_con_anteprima(client, db, admin, auth, crea_utente, crea_corso, crea_ufficio, crea_percorso):
    configura(db, crea_utente, crea_corso, crea_ufficio, crea_percorso)
    file = client.get("/api/admin/configurazione/export", headers=auth(admin)).json()
    cancella_configurazione(db)
    db.query(Azienda).delete()
    db.commit()

    anteprima = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": file}).json()
    assert anteprima["applicato"] is False
    assert sorted(anteprima["sezioni"]["gruppi"]["creati"]) == ["Direzione", "Direzione / Legale"]
    assert len(anteprima["sezioni"]["corsi"]["creati"]) == 2 and anteprima["totali"] == {"creati": 6, "aggiornati": 1}  # 2 gruppi, 1 società, 2 corsi, 1 percorso; i dati aziendali si aggiornano
    assert db.query(Corso).count() == 0 and db.query(Group).count() == 0       # l'anteprima non scrive nulla

    fatto = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": file, "applica": True}).json()
    assert fatto["applicato"] is True and fatto["totali"] == anteprima["totali"]  # l'anteprima diceva il vero
    assert db.query(Corso).count() == 2 and db.query(Organizzazione).count() == 1
    assert db.query(Azienda).one().nome_piattaforma == "Formazione Acme"
    legale = db.query(Group).filter(Group.name == "Legale").one()
    direzione = db.query(Group).filter(Group.name == "Direzione").one()
    assert legale.parent_id == direzione.id and direzione.is_ufficio and direzione.responsabile_id is not None
    privacy = db.query(Corso).filter(Corso.titolo == "Privacy").one()
    assert privacy.rinnovo_automatico and privacy.rinnovo_giorni_anticipo == 45 and privacy.validita_mesi == 24
    p = db.query(PercorsoFormativo).one()
    assert p.trigger_gruppo_id == legale.id and db.query(PercorsoStep).count() == 2 and db.query(PercorsoStepPrerequisito).count() == 1
    assert any("test finale" in a for a in fatto["avvisi"])                       # i test non sono nel file
    assert db.query(AuditLog).filter(AuditLog.action == "CONFIG_IMPORT").count() == 1


def test_reimportare_lo_stesso_file_non_cambia_nulla(client, db, admin, auth, crea_utente, crea_corso, crea_ufficio, crea_percorso):
    configura(db, crea_utente, crea_corso, crea_ufficio, crea_percorso)
    file = client.get("/api/admin/configurazione/export", headers=auth(admin)).json()
    r = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": file, "applica": True}).json()
    assert r["totali"] == {"creati": 0, "aggiornati": 0}
    assert db.query(Corso).count() == 2 and db.query(Group).count() == 2


def test_aggiorna_senza_cancellare(client, db, admin, auth, crea_utente, crea_corso, crea_ufficio, crea_percorso):
    configura(db, crea_utente, crea_corso, crea_ufficio, crea_percorso)
    file = client.get("/api/admin/configurazione/export", headers=auth(admin)).json()
    privacy = db.query(Corso).filter(Corso.titolo == "Privacy").one()
    privacy.validita_mesi, privacy.versione = 12, 5
    db.add(Corso(titolo="Corso extra locale"))
    db.commit()
    r = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": file, "applica": True}).json()
    agg = r["sezioni"]["corsi"]["aggiornati"]
    assert [a["nome"] for a in agg] == ["Privacy"] and agg[0]["campi"] == ["validita_mesi"]
    db.refresh(privacy)
    assert privacy.validita_mesi == 24 and privacy.versione == 5            # la versione di un corso esistente non si tocca
    assert db.query(Corso).filter(Corso.titolo == "Corso extra locale").count() == 1  # niente viene cancellato


def test_riferimenti_mancanti_diventano_avvisi(client, db, admin, auth, crea_utente, crea_corso, crea_ufficio, crea_percorso):
    configura(db, crea_utente, crea_corso, crea_ufficio, crea_percorso)
    file = client.get("/api/admin/configurazione/export", headers=auth(admin)).json()
    cancella_configurazione(db)
    db.query(User).filter(User.email == "resp@acme.it").delete()
    db.commit()
    file["percorsi"][0]["passi"].append({"corso": "Corso che non esiste", "ordine": 9, "richiede": []})
    r = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": file, "applica": True}).json()
    testo = " ".join(r["avvisi"])
    assert "resp@acme.it" in testo and "Corso che non esiste" in testo
    assert db.query(Group).filter(Group.name == "Direzione").one().responsabile_id is None


def test_file_non_valido_o_troppo_recente(client, admin, auth):
    assert client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": {"ciao": 1}}).status_code == 400
    r = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": {"formato": "elearning-configurazione", "schema": 99}})
    assert r.status_code == 400 and "più recente" in r.json()["detail"]
    r = client.post("/api/admin/configurazione/import", headers=auth(admin),
                    json={"contenuto": {"formato": "elearning-configurazione", "schema": 1, "gruppi": [{"nome": "senza percorso"}]}})
    assert r.status_code == 400 and "percorso" in r.json()["detail"]


def test_elenchi_in_tabella_con_i_permessi_giusti(client, db, admin, formazione, utente, auth, crea_corso, crea_ufficio, crea_percorso, crea_utente):
    c = crea_corso("Sicurezza", validita_mesi=12)
    crea_percorso([c], [], nome="Percorso A")
    crea_ufficio("Ufficio X")
    db.add(Organizzazione(ragione_sociale="Ente Beta"))
    db.commit()
    for percorso, ammessi, contiene in (("/api/auth/users/export", {"admin"}, "Admin Test"), ("/api/admin/gruppi-export", {"admin"}, "Ufficio X"),
                                         ("/api/organizzazioni-export/elenco", {"admin"}, "Ente Beta"),
                                         ("/api/corsi-export/elenco", {"admin", "formazione"}, "Sicurezza"), ("/api/corsi-export/percorsi", {"admin", "formazione"}, "Percorso A")):
        for nome, persona in {"admin": admin, "formazione": formazione, "utente": utente}.items():
            r = client.get(percorso, headers=auth(persona))
            assert (r.status_code == 200) == (nome in ammessi), f"{nome} {percorso}: {r.status_code}"
            if nome == "admin":
                assert contiene in r.text
        assert client.get(percorso, params={"formato": "xlsx"}, headers=auth(admin)).status_code == 200
