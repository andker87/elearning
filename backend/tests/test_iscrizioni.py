"""Capienza, lista d'attesa e promozione."""
from app.models.edizione import StatoEdizione as SE
from app.models.iscrizione import Iscrizione, StatoIscrizione as S


def iscrivi(client, auth, admin, edizione, *utenti):
    return client.post(f"/api/edizioni/{edizione.id}/iscrizioni", headers=auth(admin), json=[str(u.id) for u in utenti])


def stato(db, edizione, utente):
    db.expire_all()
    return db.query(Iscrizione).filter(Iscrizione.edizione_id == edizione.id, Iscrizione.user_id == utente.id).one().stato


def test_posti_esauriti_senza_lista_d_attesa_rifiuta(client, db, auth, admin, crea_utente, crea_corso, crea_edizione):
    ed = crea_edizione(crea_corso(), stato=SE.pianificata, posti_max=1)
    uno, due = crea_utente("uno@test.it"), crea_utente("due@test.it")
    assert iscrivi(client, auth, admin, ed, uno).status_code == 200
    r = iscrivi(client, auth, admin, ed, due)
    assert r.status_code == 200 and r.json()["iscritti"] == [] and r.json()["non_iscritti"][0]["user_id"] == str(due.id)
    assert db.query(Iscrizione).filter(Iscrizione.user_id == due.id).count() == 0


def test_lista_d_attesa_e_promozione_in_ordine(client, db, auth, admin, crea_utente, crea_corso, crea_edizione):
    ed = crea_edizione(crea_corso(), stato=SE.pianificata, posti_max=1, lista_attesa_abilitata=True)
    uno, due, tre = (crea_utente(f"{n}@test.it") for n in ("uno", "due", "tre"))
    for u in (uno, due, tre):
        assert iscrivi(client, auth, admin, ed, u).status_code == 200
    assert [stato(db, ed, u) for u in (uno, due, tre)] == [S.iscritto, S.in_lista_attesa, S.in_lista_attesa]

    i_uno = db.query(Iscrizione).filter(Iscrizione.user_id == uno.id).one()
    assert client.post(f"/api/edizioni/{ed.id}/iscrizioni/{i_uno.id}/annulla", headers=auth(admin)).status_code == 200
    assert [stato(db, ed, u) for u in (uno, due, tre)] == [S.annullato, S.iscritto, S.in_lista_attesa]  # prima chi era arrivato prima


def test_iscrizione_doppia_ignorata(client, db, auth, admin, utente, crea_corso, crea_edizione):
    ed = crea_edizione(crea_corso(), stato=SE.pianificata)
    iscrivi(client, auth, admin, ed, utente)
    iscrivi(client, auth, admin, ed, utente)
    assert db.query(Iscrizione).filter(Iscrizione.user_id == utente.id).count() == 1


def test_un_utente_semplice_non_iscrive_altri(client, auth, utente, crea_utente, crea_corso, crea_edizione):
    ed = crea_edizione(crea_corso(), stato=SE.pianificata)
    altro = crea_utente("altro@test.it")
    r = client.post(f"/api/edizioni/{ed.id}/iscrizioni", headers=auth(utente), json=[str(altro.id)])
    assert r.status_code == 403


def test_annullare_l_iscrizione_di_un_altro_e_vietato(client, db, auth, utente, crea_utente, crea_corso, crea_edizione, crea_iscrizione):
    ed = crea_edizione(crea_corso(), stato=SE.pianificata)
    altro = crea_utente("altro@test.it")
    i = crea_iscrizione(ed, altro)
    assert client.post(f"/api/edizioni/{ed.id}/iscrizioni/{i.id}/annulla", headers=auth(utente)).status_code == 403


def test_un_iscrizione_annullata_sparisce_da_i_miei_corsi(client, db, auth, admin, crea_corso, crea_edizione):
    """Se mi iscrivo per errore e poi mi tolgo, non devo piu' comparire tra i miei corsi (ne' nello storico)."""
    ed = crea_edizione(crea_corso("Corso per errore"), stato=SE.pianificata)
    assert iscrivi(client, auth, admin, ed, admin).status_code == 200
    mie = lambda: client.get("/api/edizioni/mie/iscrizioni", headers=auth(admin)).json()
    assert [i["corso_titolo"] for i in mie()] == ["Corso per errore"]
    i = db.query(Iscrizione).filter(Iscrizione.user_id == admin.id).one()
    assert client.post(f"/api/edizioni/{ed.id}/iscrizioni/{i.id}/annulla", headers=auth(admin)).status_code == 200
    assert mie() == []                                                    # annullata: non e' piu' mia
    assert iscrivi(client, auth, admin, ed, admin).status_code == 200     # e se mi iscrivo di nuovo, ricompare (una sola volta)
    assert [x["stato"] for x in mie()] == ["iscritto"]
