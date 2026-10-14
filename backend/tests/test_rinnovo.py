"""Rinnovo automatico dei corsi con scadenza."""
from app.models.audit import AuditLog
from app.models.edizione import StatoEdizione as SE
from app.models.iscrizione import Iscrizione, StatoIscrizione as S
from app.models.notification import Notification
from app.services.rinnovo import esegui_rinnovi


def corso_rinnovabile(crea_corso, **kw):
    return crea_corso("Sicurezza", validita_mesi=12, rinnovo_automatico=True, rinnovo_giorni_anticipo=30, **kw)


def apri_sessione(crea_edizione, corso, giorni=20, **kw):
    from conftest import adesso
    from datetime import timedelta
    return crea_edizione(corso, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=giorni), **kw)


def completato(crea_edizione, crea_iscrizione, corso, utente, giorni_fa):
    return crea_iscrizione(crea_edizione(corso), utente, S.completato, giorni_fa=giorni_fa)


def test_iscrive_chi_sta_per_scadere(db, utente, crea_corso, crea_edizione, crea_iscrizione):
    corso = corso_rinnovabile(crea_corso)
    completato(crea_edizione, crea_iscrizione, corso, utente, giorni_fa=345)  # scade tra ~20 giorni
    sessione = apri_sessione(crea_edizione, corso)
    assert "iscritti 1" in esegui_rinnovi(db)
    nuova = db.query(Iscrizione).filter(Iscrizione.edizione_id == sessione.id).one()
    assert nuova.user_id == utente.id and nuova.stato == S.iscritto
    assert db.query(Notification).filter(Notification.user_id == utente.id, Notification.tipo == "rinnovo_automatico").count() == 1
    assert db.query(AuditLog).filter(AuditLog.action == "RINNOVO_AUTOMATICO").count() == 1


def test_e_idempotente(db, utente, crea_corso, crea_edizione, crea_iscrizione):
    corso = corso_rinnovabile(crea_corso)
    completato(crea_edizione, crea_iscrizione, corso, utente, giorni_fa=345)
    apri_sessione(crea_edizione, corso)
    esegui_rinnovi(db)
    assert "iscritti 0" in esegui_rinnovi(db)
    assert db.query(Iscrizione).filter(Iscrizione.user_id == utente.id, Iscrizione.stato == S.iscritto).count() == 1


def test_chi_non_e_in_scadenza_non_viene_toccato(db, utente, crea_corso, crea_edizione, crea_iscrizione):
    corso = corso_rinnovabile(crea_corso)
    completato(crea_edizione, crea_iscrizione, corso, utente, giorni_fa=100)  # scade tra molti mesi
    apri_sessione(crea_edizione, corso)
    assert "iscritti 0" in esegui_rinnovi(db) and db.query(Iscrizione).filter(Iscrizione.stato == S.iscritto).count() == 0


def test_include_anche_chi_e_gia_scaduto(db, utente, crea_corso, crea_edizione, crea_iscrizione):
    corso = corso_rinnovabile(crea_corso)
    completato(crea_edizione, crea_iscrizione, corso, utente, giorni_fa=500)
    apri_sessione(crea_edizione, corso)
    assert "iscritti 1" in esegui_rinnovi(db)


def test_il_rinnovo_spento_non_fa_nulla(db, utente, crea_corso, crea_edizione, crea_iscrizione):
    corso = crea_corso("Sicurezza", validita_mesi=12)  # rinnovo_automatico spento di default
    completato(crea_edizione, crea_iscrizione, corso, utente, giorni_fa=345)
    apri_sessione(crea_edizione, corso)
    assert "iscritti 0" in esegui_rinnovi(db)


def test_chi_e_gia_iscritto_a_una_sessione_non_viene_duplicato(db, utente, crea_corso, crea_edizione, crea_iscrizione):
    corso = corso_rinnovabile(crea_corso)
    completato(crea_edizione, crea_iscrizione, corso, utente, giorni_fa=345)
    gia = apri_sessione(crea_edizione, corso, giorni=10)
    crea_iscrizione(gia, utente)
    apri_sessione(crea_edizione, corso, giorni=40)
    assert "iscritti 0" in esegui_rinnovi(db)


def test_scelta_della_sessione_piu_vicina_e_salto_di_quelle_piene(db, utente, crea_utente, crea_corso, crea_edizione, crea_iscrizione):
    corso = corso_rinnovabile(crea_corso)
    completato(crea_edizione, crea_iscrizione, corso, utente, giorni_fa=345)
    piena = apri_sessione(crea_edizione, corso, giorni=5, posti_max=1)
    crea_iscrizione(piena, crea_utente("altro@test.it"))
    lontana = apri_sessione(crea_edizione, corso, giorni=60)
    esegui_rinnovi(db)
    assert db.query(Iscrizione).filter(Iscrizione.edizione_id == lontana.id, Iscrizione.user_id == utente.id).count() == 1
    assert db.query(Iscrizione).filter(Iscrizione.edizione_id == piena.id).count() == 1  # la piena e' rimasta com'era


def test_sessione_piena_con_lista_d_attesa(db, utente, crea_utente, crea_corso, crea_edizione, crea_iscrizione):
    corso = corso_rinnovabile(crea_corso)
    completato(crea_edizione, crea_iscrizione, corso, utente, giorni_fa=345)
    piena = apri_sessione(crea_edizione, corso, posti_max=1, lista_attesa_abilitata=True)
    crea_iscrizione(piena, crea_utente("altro@test.it"))
    assert "lista d'attesa 1" in esegui_rinnovi(db)
    assert db.query(Iscrizione).filter(Iscrizione.user_id == utente.id, Iscrizione.stato == S.in_lista_attesa).count() == 1


def test_senza_sessioni_avvisa_la_formazione_una_volta_a_settimana(db, utente, formazione, crea_corso, crea_edizione, crea_iscrizione):
    corso = corso_rinnovabile(crea_corso)
    completato(crea_edizione, crea_iscrizione, corso, utente, giorni_fa=345)
    assert "senza sessione disponibile 1" in esegui_rinnovi(db)
    esegui_rinnovi(db)
    avvisi = db.query(Notification).filter(Notification.user_id == formazione.id, Notification.tipo == "rinnovo_senza_sessione").all()
    assert len(avvisi) == 1 and "nessuna sessione disponibile" in avvisi[0].testo
    assert db.query(Iscrizione).filter(Iscrizione.stato == S.iscritto).count() == 0


def test_sessioni_passate_o_annullate_non_contano(db, utente, crea_corso, crea_edizione, crea_iscrizione):
    corso = corso_rinnovabile(crea_corso)
    completato(crea_edizione, crea_iscrizione, corso, utente, giorni_fa=345)
    apri_sessione(crea_edizione, corso, giorni=-10)                     # gia' passata
    crea_edizione(corso, stato=SE.annullata)
    assert "iscritti 0" in esegui_rinnovi(db)


def test_utente_disattivato_non_viene_iscritto(db, crea_utente, crea_corso, crea_edizione, crea_iscrizione):
    corso = corso_rinnovabile(crea_corso)
    uscito = crea_utente("uscito@test.it", is_active=False)
    completato(crea_edizione, crea_iscrizione, corso, uscito, giorni_fa=345)
    apri_sessione(crea_edizione, corso)
    assert "iscritti 0" in esegui_rinnovi(db)


def test_videocorso_sempre_aperto_senza_data(db, utente, crea_corso, crea_edizione, crea_iscrizione):
    corso = corso_rinnovabile(crea_corso)
    completato(crea_edizione, crea_iscrizione, corso, utente, giorni_fa=345)
    video = crea_edizione(corso, stato=SE.pianificata, data_inizio=None)
    assert "iscritti 1" in esegui_rinnovi(db)
    assert db.query(Iscrizione).filter(Iscrizione.edizione_id == video.id).count() == 1


# --- impostazione dal corso ----------------------------------------------------------------

def test_api_il_rinnovo_richiede_una_validita(client, formazione, auth):
    r = client.post("/api/corsi", headers=auth(formazione), json={"titolo": "X", "rinnovo_automatico": True})
    assert r.status_code == 422
    ok = client.post("/api/corsi", headers=auth(formazione), json={"titolo": "X", "validita_mesi": 12, "rinnovo_automatico": True, "rinnovo_giorni_anticipo": 45})
    assert ok.status_code == 200 and ok.json()["rinnovo_automatico"] is True and ok.json()["rinnovo_giorni_anticipo"] == 45
    assert client.post("/api/corsi", headers=auth(formazione), json={"titolo": "Y", "validita_mesi": 12, "rinnovo_giorni_anticipo": 0}).status_code == 422


def test_api_spento_di_default_e_anteprima(client, db, formazione, utente, auth, crea_edizione, crea_iscrizione):
    c = client.post("/api/corsi", headers=auth(formazione), json={"titolo": "Sic", "validita_mesi": 12}).json()
    assert c["rinnovo_automatico"] is False and c["rinnovo_giorni_anticipo"] == 30
    from app.models.corso import Corso
    corso = db.query(Corso).filter(Corso.titolo == "Sic").one()
    completato(crea_edizione, crea_iscrizione, corso, utente, giorni_fa=350)
    apri_sessione(crea_edizione, corso, posti_max=5)
    a = client.get(f"/api/corsi/{c['id']}/rinnovo/anteprima", headers=auth(formazione)).json()
    assert [p["nome"] for p in a["persone"]] == [utente.full_name] and a["sessioni"][0]["posti_liberi"] == 5
    assert db.query(Iscrizione).filter(Iscrizione.stato == S.iscritto).count() == 0  # l'anteprima non iscrive nessuno
    assert client.get(f"/api/corsi/{c['id']}/rinnovo/anteprima", headers=auth(utente)).status_code == 403


def test_modificare_il_template_non_azzera_il_rinnovo(client, formazione, auth):
    c = client.post("/api/corsi", headers=auth(formazione), json={"titolo": "Z", "validita_mesi": 6, "rinnovo_automatico": True}).json()
    r = client.put(f"/api/corsi/{c['id']}", headers=auth(formazione), json={**c, "certificato_template_id": None})
    assert r.json()["rinnovo_automatico"] is True
