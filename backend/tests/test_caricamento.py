"""Caricamento in blocco: stessi numeri delle funzioni che lavorano su una riga alla volta."""
from app.models.edizione import StatoEdizione as SE
from app.models.iscrizione import StatoIscrizione as S
from app.services.caricamento import per_id
from app.services.iscrizioni import posti_occupati, posti_occupati_per_sessione


def test_i_posti_occupati_in_blocco_coincidono_con_quelli_uno_a_uno(db, crea_utente, crea_corso, crea_edizione, crea_iscrizione):
    corso = crea_corso("Corso")
    a, b, vuota = (crea_edizione(corso, stato=SE.pianificata) for _ in range(3))
    for stato in (S.iscritto, S.completato, S.annullato, S.in_lista_attesa):
        crea_iscrizione(a, crea_utente(), stato=stato)
    crea_iscrizione(b, crea_utente(), stato=S.non_completato)
    blocco = posti_occupati_per_sessione(db, [a.id, b.id, vuota.id])
    assert blocco.get(str(a.id), 0) == posti_occupati(db, a.id) == 2          # annullata e lista d'attesa non occupano posto
    assert blocco.get(str(b.id), 0) == posti_occupati(db, b.id) == 1
    assert blocco.get(str(vuota.id), 0) == posti_occupati(db, vuota.id) == 0
    assert posti_occupati_per_sessione(db, []) == {}


def test_per_id_ignora_i_nulli_e_i_mancanti(db, crea_corso):
    c = crea_corso("Corso")
    assert list(per_id(db, type(c), [c.id, None, c.id]).keys()) == [str(c.id)]
    assert per_id(db, type(c), []) == {}


def test_le_sessioni_imminenti_mostrano_corso_e_posti(client, auth, formazione, utente, crea_utente, db, crea_corso, crea_edizione, crea_iscrizione):
    from datetime import timedelta
    from conftest import adesso
    corso = crea_corso("Antincendio")
    e = crea_edizione(corso, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=3), posti_max=5)
    crea_iscrizione(e, utente); crea_iscrizione(e, crea_utente(), stato=S.annullato)
    lontana = crea_edizione(corso, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=60))
    r = client.get("/api/dashboard/formazione/sessioni-imminenti", headers=auth(formazione))
    assert r.status_code == 200, r.text
    righe = r.json()
    assert [x["id"] for x in righe] == [str(e.id)] and str(lontana.id) not in [x["id"] for x in righe]
    assert righe[0]["corso_titolo"] == "Antincendio" and righe[0]["n_iscritti"] == 1 and righe[0]["posti_liberi"] == 4
