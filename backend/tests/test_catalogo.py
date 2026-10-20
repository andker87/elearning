"""2.7.0: catalogo per tutti e sessioni video «sempre aperte» con attestato automatico."""
from datetime import timedelta

import pytest

from app.models.certificato import Certificato
from app.models.edizione import ModalitaErogazione as M, StatoEdizione as SE
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
