"""2.7.0: catalogo per tutti e sessioni video «sempre aperte» con attestato automatico."""
from datetime import timedelta

import pytest

from app.models.certificato import Certificato
from app.models.edizione import Edizione, ModalitaErogazione as M, StatoEdizione as SE
from app.models.evidenza import Evidenza
from app.models.iscrizione import Iscrizione, StatoIscrizione as S
from app.models.test import Domanda, OpzioneRisposta, Test
from app.models.video import StatoVideo, VideoContenuto

from conftest import adesso


@pytest.fixture
def video_corto(db):
    v = VideoContenuto(titolo="Sicurezza", stato=StatoVideo.pronto, durata_secondi=100)
    db.add(v); db.commit()
    return v


@pytest.fixture
def sempre(db, crea_corso, crea_edizione, video_corto):
    """Corso con auto-iscrizione e sessione video sempre aperta (pianificata, senza date)."""
    c = crea_corso("Corso sempre disponibile"); c.permetti_autoiscrizione = True; db.commit()
    return crea_edizione(c, stato=SE.pianificata, modalita=M.video, data_inizio=None, sempre_aperta=True, video_id=video_corto.id)


def guarda(client, auth, utente, iscrizione, secondo):
    return client.post(f"/api/iscrizioni/{iscrizione}/progresso", headers=auth(utente), json={"secondo_corrente": secondo})


def test_la_sessione_sempre_aperta_e_solo_video_e_senza_date(client, auth, formazione, crea_corso, video_corto):
    cid = str(crea_corso("Corso").id)
    r = client.post("/api/edizioni", headers=auth(formazione), json={"corso_id": cid, "modalita": "presenza", "sempre_aperta": True})
    assert r.status_code == 422
    r = client.post("/api/edizioni", headers=auth(formazione), json={
        "corso_id": cid, "modalita": "video", "video_id": str(video_corto.id), "sempre_aperta": True,
        "data_inizio": "2030-01-01T10:00:00Z", "posti_max": 5, "lista_attesa_abilitata": True})
    assert r.status_code == 200, r.text
    e = r.json()
    assert e["sempre_aperta"] is True and e["data_inizio"] is None and e["data_fine"] is None and e["posti_max"] is None and e["lista_attesa_abilitata"] is False
    copia = client.post(f"/api/edizioni/{e['id']}/duplica", headers=auth(formazione)).json()
    assert copia["sempre_aperta"] is True


def test_il_catalogo_mostra_solo_cio_che_si_puo_scegliere(client, auth, utente, db, crea_corso, crea_edizione, sempre):
    chiuso = crea_corso("Corso chiuso"); crea_edizione(chiuso, stato=SE.pianificata)                                   # niente auto-iscrizione
    aperto = crea_corso("Con data"); aperto.permetti_autoiscrizione = True
    crea_edizione(aperto, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=5), posti_max=10)
    passato = crea_corso("Passato"); passato.permetti_autoiscrizione = True
    crea_edizione(passato, stato=SE.pianificata, data_inizio=adesso() - timedelta(days=9), data_fine=adesso() - timedelta(days=8))
    bozza = crea_corso("Bozza"); bozza.permetti_autoiscrizione = True; crea_edizione(bozza, stato=SE.bozza)
    inattivo = crea_corso("Inattivo"); inattivo.permetti_autoiscrizione = True; inattivo.is_active = False
    crea_edizione(inattivo, stato=SE.pianificata)
    db.commit()
    r = client.get("/api/catalogo", headers=auth(utente)).json()
    assert [x["corso_titolo"] for x in r] == ["Corso sempre disponibile", "Con data"]          # sempre disponibili per prime
    assert r[0]["sempre_aperta"] is True and r[0]["mio_stato"] is None and r[1]["posti_liberi"] == 10
    assert client.get("/api/catalogo").status_code in (401, 403)


def test_chi_guarda_il_video_fino_in_fondo_riceve_l_attestato(client, auth, utente, db, sempre):
    assert client.post(f"/api/autoiscrizioni/edizioni/{sempre.id}", headers=auth(utente)).json()["stato"] == "iscritto"
    i = db.query(Iscrizione).filter(Iscrizione.user_id == utente.id).one()
    assert client.get("/api/catalogo", headers=auth(utente)).json()[0]["mio_stato"] == "iscritto"
    r = guarda(client, auth, utente, i.id, 30).json()
    assert r["completato"] is False                                                            # visto solo in parte
    db.expire_all(); assert db.get(Iscrizione, i.id).stato == S.iscritto and db.query(Certificato).count() == 0
    # l'anti-skip tiene conto di quanto si e' guardato: si avanza a piccoli passi come fa il player
    secondo, fatto = 30, None
    while secondo < 90:
        secondo += 10
        r = guarda(client, auth, utente, i.id, secondo).json()
        fatto = fatto or (r if r["completato"] else None)
    assert fatto and fatto["certificato_id"] and secondo >= 80
    db.expire_all()
    i = db.get(Iscrizione, i.id)
    assert i.stato == S.completato and i.completato_at is not None and i.versione_corso == 1
    assert db.query(Certificato).count() == 1
    assert guarda(client, auth, utente, i.id, 95).json()["completato"] is False                # nessun secondo attestato
    assert db.query(Certificato).count() == 1
    assert client.get("/api/catalogo", headers=auth(utente)).json()[0]["mio_stato"] == "completato"


def test_con_il_test_finale_servono_video_e_test(client, auth, utente, db, sempre):
    from app.models.corso import AzioneTestNonSuperato, Corso
    corso = db.get(Corso, sempre.corso_id)
    corso.azione_test_non_superato = AzioneTestNonSuperato.rifai_corso      # in una sessione sempre aperta si puo' comunque riprovare
    t = Test(corso_id=corso.id, titolo="Finale", soglia_superamento_pct=60); db.add(t); db.flush()
    d = Domanda(test_id=t.id, testo="2+2?", ordine=0); db.add(d); db.flush()
    giusta, sbagliata = OpzioneRisposta(domanda_id=d.id, testo="4", corretta=True), OpzioneRisposta(domanda_id=d.id, testo="5", corretta=False)
    db.add_all([giusta, sbagliata]); db.commit()
    client.post(f"/api/autoiscrizioni/edizioni/{sempre.id}", headers=auth(utente))
    i = db.query(Iscrizione).filter(Iscrizione.user_id == utente.id).one()
    secondo = 0
    while secondo < 90:
        secondo += 10
        r = guarda(client, auth, utente, i.id, secondo).json()
    assert r["completato"] is False                                                            # manca il test
    sbaglio = client.post(f"/api/test/{t.id}/tenta", headers=auth(utente), json={"iscrizione_id": str(i.id), "risposte": {str(d.id): str(sbagliata.id)}}).json()
    assert sbaglio["superato"] is False
    db.expire_all(); assert db.get(Iscrizione, i.id).stato == S.iscritto and db.query(Certificato).count() == 0     # si puo' riprovare
    ok = client.post(f"/api/test/{t.id}/tenta", headers=auth(utente), json={"iscrizione_id": str(i.id), "risposte": {str(d.id): str(giusta.id)}}).json()
    assert ok["superato"] is True and ok["certificato_id"]
    db.expire_all(); assert db.get(Iscrizione, i.id).stato == S.completato and db.query(Certificato).count() == 1


def test_le_altre_sessioni_non_si_completano_da_sole(client, auth, utente, db, crea_corso, crea_edizione, crea_iscrizione, video_corto):
    c = crea_corso("Normale"); c.permetti_autoiscrizione = True; db.commit()
    e = crea_edizione(c, stato=SE.in_corso, modalita=M.video, video_id=video_corto.id)
    i = crea_iscrizione(e, utente)
    secondo = 0
    while secondo < 100:
        secondo += 10
        r = guarda(client, auth, utente, i.id, secondo).json()
    assert r["completato"] is False
    db.expire_all(); assert db.get(Iscrizione, i.id).stato == S.iscritto                       # per queste decide la chiusura


def test_alla_chiusura_un_video_visto_per_poco_non_vale_come_completato(client, auth, formazione, utente, db, crea_corso, crea_edizione, crea_iscrizione, video_corto):
    c = crea_corso("Normale"); db.commit()
    e = crea_edizione(c, stato=SE.in_corso, modalita=M.video, video_id=video_corto.id)
    i = crea_iscrizione(e, utente)
    guarda(client, auth, utente, i.id, 10)
    r = client.post(f"/api/edizioni/{e.id}/chiudi", headers=auth(formazione)).json()
    assert r["esiti"][0]["completato"] is False


def test_con_la_regola_concludi_comunque_il_test_sbagliato_non_blocca(client, auth, utente, db, sempre):
    from app.models.corso import Corso
    t = Test(corso_id=sempre.corso_id, titolo="Finale"); db.add(t); db.flush()
    d = Domanda(test_id=t.id, testo="2+2?", ordine=0); db.add(d); db.flush()
    sbagliata = OpzioneRisposta(domanda_id=d.id, testo="5", corretta=False)
    db.add_all([OpzioneRisposta(domanda_id=d.id, testo="4", corretta=True), sbagliata]); db.commit()
    assert db.get(Corso, sempre.corso_id).azione_test_non_superato.value == "concludi_comunque"      # la regola predefinita
    client.post(f"/api/autoiscrizioni/edizioni/{sempre.id}", headers=auth(utente))
    i = db.query(Iscrizione).filter(Iscrizione.user_id == utente.id).one()
    secondo = 0
    while secondo < 90:
        secondo += 10
        guarda(client, auth, utente, i.id, secondo)
    db.expire_all(); assert db.get(Iscrizione, i.id).stato == S.iscritto                    # senza tentativi il test manca ancora
    client.post(f"/api/test/{t.id}/tenta", headers=auth(utente), json={"iscrizione_id": str(i.id), "risposte": {str(d.id): str(sbagliata.id)}})
    db.expire_all(); assert db.get(Iscrizione, i.id).stato == S.completato                  # come alla chiusura di una sessione normale


# --- 2.7.1: eliminare un corso, pubblicare e ritirare le sessioni --------------------------------

def test_solo_l_admin_tecnico_elimina_un_corso_e_scrivendo_il_titolo(client, auth, admin, formazione, db, crea_corso, crea_edizione):
    from app.models.corso import Corso
    c = crea_corso("Creato per sbaglio"); crea_edizione(c, stato=SE.bozza); db.commit()
    cid = str(c.id); uuid_c = c.id
    assert client.get(f"/api/corsi/{cid}/eliminazione", headers=auth(formazione)).status_code == 403
    assert client.post(f"/api/corsi/{cid}/elimina", headers=auth(formazione), json={"conferma": "Creato per sbaglio"}).status_code == 403     # la Formazione disattiva soltanto
    esame = client.get(f"/api/corsi/{cid}/eliminazione", headers=auth(admin)).json()
    assert esame["eliminabile"] is True and esame["sessioni"] == 1
    assert client.post(f"/api/corsi/{cid}/elimina", headers=auth(admin), json={"conferma": "creato"}).status_code == 400                       # titolo diverso
    assert db.get(Corso, uuid_c) is not None
    assert client.post(f"/api/corsi/{cid}/elimina", headers=auth(admin), json={"conferma": "Creato per sbaglio"}).status_code == 200
    db.expire_all(); assert db.get(Corso, uuid_c) is None and db.query(Edizione).count() == 0


def test_un_corso_con_formazione_registrata_non_si_elimina(client, auth, admin, utente, db, crea_corso, crea_edizione, crea_iscrizione, crea_percorso):
    from app.models.corso import Corso
    usato = crea_corso("Con iscritti"); crea_iscrizione(crea_edizione(usato, stato=SE.pianificata), utente)
    r = client.post(f"/api/corsi/{usato.id}/elimina", headers=auth(admin), json={"conferma": "Con iscritti"})
    assert r.status_code == 409 and "1 iscrizione attiva o conclusa" in r.json()["detail"] and "disattivalo" in r.json()["detail"]
    in_percorso = crea_corso("In un percorso"); crea_percorso([in_percorso], [utente])
    r = client.post(f"/api/corsi/{in_percorso.id}/elimina", headers=auth(admin), json={"conferma": "In un percorso"})
    assert r.status_code == 409 and "percorso" in r.json()["detail"]
    db.expire_all(); assert db.query(Corso).count() == 2


def test_le_iscrizioni_annullate_non_impediscono_l_eliminazione(client, auth, admin, utente, db, crea_corso, crea_edizione, crea_iscrizione):
    from app.models.corso import Corso
    from app.models.iscrizione import Iscrizione
    c = crea_corso("Provato e annullato"); e = crea_edizione(c, stato=SE.pianificata)
    i = crea_iscrizione(e, utente, stato=S.annullato)
    t = Test(corso_id=c.id, titolo="Finale"); db.add(t); db.commit()
    uuid_c, uuid_i = c.id, i.id
    assert client.post(f"/api/corsi/{c.id}/elimina", headers=auth(admin), json={"conferma": "Provato e annullato"}).status_code == 200
    db.expire_all()
    assert db.get(Corso, uuid_c) is None and db.get(Iscrizione, uuid_i) is None and db.query(Test).count() == 0


def test_una_sessione_pubblicata_torna_in_bozza_solo_se_vuota(client, auth, formazione, utente, db, crea_corso, crea_edizione, crea_iscrizione):
    from app.models.edizione import Edizione
    e = crea_edizione(crea_corso("Corso"), stato=SE.bozza)
    assert client.post(f"/api/edizioni/{e.id}/pianifica", headers=auth(formazione)).status_code == 200
    db.expire_all(); assert db.get(Edizione, e.id).stato == SE.pianificata
    i = crea_iscrizione(e, utente)
    assert client.post(f"/api/edizioni/{e.id}/bozza", headers=auth(formazione)).status_code == 400
    assert client.post(f"/api/edizioni/{e.id}/bozza", headers=auth(utente)).status_code == 403
    i.stato = S.annullato; db.commit()
    assert client.post(f"/api/edizioni/{e.id}/bozza", headers=auth(formazione)).status_code == 200
    db.expire_all(); assert db.get(Edizione, e.id).stato == SE.bozza
    chiusa = crea_edizione(crea_corso("Altro"), stato=SE.chiusa)
    assert client.post(f"/api/edizioni/{chiusa.id}/bozza", headers=auth(formazione)).status_code == 400


def test_una_sessione_sempre_disponibile_e_aperta_a_tutti_anche_se_il_corso_non_ha_l_auto_iscrizione(client, auth, utente, db, crea_corso, crea_edizione, video_corto):
    c = crea_corso("Corso senza auto-iscrizione")
    libera = crea_edizione(c, stato=SE.pianificata, modalita=M.video, data_inizio=None, sempre_aperta=True, video_id=video_corto.id)
    datata = crea_edizione(c, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=4))
    catalogo = client.get("/api/catalogo", headers=auth(utente)).json()
    assert [x["id"] for x in catalogo] == [str(libera.id)]                                      # quella con data resta su invito
    assert client.post(f"/api/autoiscrizioni/edizioni/{libera.id}", headers=auth(utente)).json()["stato"] == "iscritto"
    assert client.post(f"/api/autoiscrizioni/edizioni/{datata.id}", headers=auth(utente)).status_code == 403
    d = client.get(f"/api/edizioni/{libera.id}", headers=auth(utente)).json()
    assert d["in_catalogo"] is True and d["corso_permetti_autoiscrizione"] is True and d["corso_autoiscrizione_attiva"] is False
    assert client.get(f"/api/edizioni/{datata.id}", headers=auth(utente)).json()["in_catalogo"] is False


def test_si_puo_rendere_sempre_disponibile_una_sessione_video_gia_creata(client, auth, formazione, utente, db, crea_corso, crea_edizione, video_corto):
    c = crea_corso("Comunicazione efficace")
    e = crea_edizione(c, stato=SE.pianificata, modalita=M.video, data_inizio=None, video_id=video_corto.id)
    assert client.get("/api/catalogo", headers=auth(utente)).json() == []
    r = client.put(f"/api/edizioni/{e.id}", headers=auth(formazione), json={"corso_id": str(c.id), "modalita": "video", "video_id": str(video_corto.id), "sempre_aperta": True})
    assert r.status_code == 200 and r.json()["in_catalogo"] is True
    assert [x["corso_titolo"] for x in client.get("/api/catalogo", headers=auth(utente)).json()] == ["Comunicazione efficace"]


def test_eliminare_una_sessione(client, auth, admin, formazione, utente, db, crea_corso, crea_edizione, crea_iscrizione):
    c = crea_corso("Corso")
    vuota = crea_edizione(c, stato=SE.bozza)
    assert client.get(f"/api/edizioni/{vuota.id}/eliminazione", headers=auth(formazione)).json()["eliminabile"] is True
    assert client.post(f"/api/edizioni/{vuota.id}/elimina", headers=auth(utente), json={}).status_code == 403
    assert client.post(f"/api/edizioni/{vuota.id}/elimina", headers=auth(formazione), json={}).status_code == 200            # la Formazione toglie quelle vuote
    assert db.query(Edizione).count() == 0
    con_iscritti = crea_edizione(c, stato=SE.pianificata); uuid_e = con_iscritti.id
    crea_iscrizione(con_iscritti, utente)
    r = client.post(f"/api/edizioni/{uuid_e}/elimina", headers=auth(formazione), json={"conferma": "ELIMINA"})
    assert r.status_code == 403 and "admin tecnico" in r.json()["detail"]                                                       # con iscritti no
    assert client.post(f"/api/edizioni/{uuid_e}/elimina", headers=auth(admin), json={}).status_code == 400                    # serve ELIMINA
    assert db.get(Edizione, uuid_e) is not None
    assert client.post(f"/api/edizioni/{uuid_e}/elimina", headers=auth(admin), json={"conferma": "ELIMINA"}).status_code == 200
    db.expire_all(); assert db.query(Edizione).count() == 0 and db.query(Iscrizione).count() == 0


def test_una_sessione_chiusa_o_con_attestati_non_si_elimina(client, auth, admin, utente, db, crea_corso, crea_edizione, crea_iscrizione):
    c = crea_corso("Corso")
    chiusa = crea_edizione(c, stato=SE.chiusa)
    r = client.post(f"/api/edizioni/{chiusa.id}/elimina", headers=auth(admin), json={"conferma": "ELIMINA"})
    assert r.status_code == 409 and "chiusa" in r.json()["detail"]
    aperta = crea_edizione(c, stato=SE.in_corso)
    i = crea_iscrizione(aperta, utente, stato=S.completato)
    db.add(Certificato(iscrizione_id=i.id, codice_verifica="ABC123", pdf_path="/tmp/x.pdf")); db.commit()
    r = client.post(f"/api/edizioni/{aperta.id}/elimina", headers=auth(admin), json={"conferma": "ELIMINA"})
    assert r.status_code == 409 and "attestat" in r.json()["detail"]
    assert db.query(Edizione).count() == 2
