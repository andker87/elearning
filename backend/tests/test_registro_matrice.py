"""Stati di compliance del registro e matrice formativa."""
from app.models.iscrizione import StatoIscrizione as S


def stati_registro(client, formazione, auth, **params):
    r = client.get("/api/registro", headers=auth(formazione), params=params)
    assert r.status_code == 200
    return {(x["persona"], x["corso"]): x["stato_compliance"] for x in r.json()}


def test_stati_del_registro(client, formazione, auth, crea_utente, crea_corso, crea_edizione, crea_iscrizione):
    sic = crea_corso("Sicurezza", validita_mesi=12)
    pri = crea_corso("Privacy")  # nessuna scadenza
    e_sic, e_pri = crea_edizione(sic), crea_edizione(pri)
    a, b, c, d = (crea_utente(f"{n}@test.it", full_name=f"Persona {n.upper()}") for n in "abcd")
    crea_iscrizione(e_sic, a, S.completato, giorni_fa=180)   # entro i 12 mesi
    crea_iscrizione(e_sic, b, S.completato, giorni_fa=400)   # oltre i 12 mesi
    crea_iscrizione(e_pri, a, S.completato, giorni_fa=2000)  # senza scadenza: resta valido
    crea_iscrizione(e_pri, c, S.non_completato)
    crea_iscrizione(e_pri, d, S.iscritto)
    stati = stati_registro(client, formazione, auth)
    assert stati[("Persona A", "Sicurezza")] == "valido"
    assert stati[("Persona B", "Sicurezza")] == "scaduto"
    assert stati[("Persona A", "Privacy")] == "valido"
    assert stati[("Persona C", "Privacy")] == "non_completato"
    assert stati[("Persona D", "Privacy")] == "in_corso"


def test_versione_obsoleta_e_da_aggiornare(client, db, formazione, auth, utente, crea_corso, crea_edizione, crea_iscrizione):
    corso = crea_corso("Normativo")
    ed = crea_edizione(corso)
    crea_iscrizione(ed, utente, S.completato, giorni_fa=10, versione=1)
    corso.versione, corso.versione_minima_valida = 2, 2  # aggiornamento che richiede la ripetizione
    db.commit()
    assert stati_registro(client, formazione, auth)[(utente.full_name, "Normativo")] == "da_aggiornare"
    corso.versione_minima_valida = 1  # aggiornamento solo informativo
    db.commit()
    riga = client.get("/api/registro", headers=auth(formazione)).json()[0]
    assert riga["stato_compliance"] == "valido" and riga["aggiornamento_disponibile"] is True


def test_iscrizioni_annullate_non_compaiono(client, formazione, auth, utente, crea_corso, crea_edizione, crea_iscrizione):
    crea_iscrizione(crea_edizione(crea_corso("Corso")), utente, S.annullato)
    assert client.get("/api/registro", headers=auth(formazione)).json() == []


def test_filtro_per_ufficio_e_per_persona(client, formazione, auth, crea_utente, crea_corso, crea_edizione, crea_iscrizione, crea_ufficio):
    ed = crea_edizione(crea_corso("Corso"))
    dentro, fuori = crea_utente("dentro@test.it", full_name="Dentro"), crea_utente("fuori@test.it", full_name="Fuori")
    crea_iscrizione(ed, dentro, S.completato, giorni_fa=1)
    crea_iscrizione(ed, fuori, S.completato, giorni_fa=1)
    uff = crea_ufficio("Ufficio A", membri=[dentro])
    assert {x["persona"] for x in client.get("/api/registro", headers=auth(formazione), params={"ufficio_id": str(uff.id)}).json()} == {"Dentro"}
    assert {x["persona"] for x in client.get("/api/registro", headers=auth(formazione), params={"user_id": str(fuori.id)}).json()} == {"Fuori"}


def test_matrice_stati_e_percentuale(client, formazione, auth, crea_utente, crea_corso, crea_edizione, crea_iscrizione, crea_percorso):
    sic = crea_corso("Sicurezza", validita_mesi=12)
    pri = crea_corso("Privacy")
    e_sic, e_pri = crea_edizione(sic), crea_edizione(pri)
    a, b, c, d = (crea_utente(f"{n}@test.it", full_name=f"Persona {n.upper()}") for n in "abcd")
    crea_percorso([sic, pri], [a, b, c, d])
    crea_iscrizione(e_sic, a, S.completato, giorni_fa=10)    # valido
    crea_iscrizione(e_pri, a, S.completato, giorni_fa=10)
    crea_iscrizione(e_sic, b, S.completato, giorni_fa=400)   # scaduto
    crea_iscrizione(e_pri, b, S.completato, giorni_fa=10)
    crea_iscrizione(e_sic, d, S.completato, giorni_fa=350)   # scade tra ~15 giorni
    crea_iscrizione(e_pri, d, S.iscritto)                    # in corso
    m = client.get("/api/registro/matrice", headers=auth(formazione)).json()
    corsi = {c["id"]: c["titolo"] for c in m["corsi"]}
    celle = {p["persona"]: {corsi[k]: v["stato"] for k, v in p["celle"].items()} for p in m["persone"]}
    assert celle["Persona A"] == {"Sicurezza": "valido", "Privacy": "valido"}
    assert celle["Persona B"] == {"Sicurezza": "scaduto", "Privacy": "valido"}
    assert celle["Persona C"] == {"Sicurezza": "mancante", "Privacy": "mancante"}  # richiesto ma mai iniziato
    assert celle["Persona D"] == {"Sicurezza": "in_scadenza", "Privacy": "in_corso"}
    r = m["riepilogo"]
    assert r["celle_obbligatorie"] == 8 and r["conformi"] == 4 and r["percentuale"] == 50.0


def test_matrice_sceglie_lo_stato_migliore_tra_piu_iscrizioni(client, formazione, auth, utente, crea_corso, crea_edizione, crea_iscrizione, crea_percorso):
    corso = crea_corso("Sicurezza", validita_mesi=12)
    crea_percorso([corso], [utente])
    crea_iscrizione(crea_edizione(corso), utente, S.completato, giorni_fa=500)  # vecchio, scaduto
    crea_iscrizione(crea_edizione(corso), utente, S.completato, giorni_fa=5)    # rinnovo recente
    cella = next(iter(client.get("/api/registro/matrice", headers=auth(formazione)).json()["persone"][0]["celle"].values()))
    assert cella["stato"] == "valido"


def test_matrice_corsi_non_richiesti_solo_su_richiesta(client, formazione, auth, utente, crea_corso, crea_edizione, crea_iscrizione):
    crea_iscrizione(crea_edizione(crea_corso("Libero")), utente, S.completato, giorni_fa=1)
    assert client.get("/api/registro/matrice", headers=auth(formazione)).json()["persone"] == []
    m = client.get("/api/registro/matrice", headers=auth(formazione), params={"solo_obbligatori": "false"}).json()
    cella = next(iter(m["persone"][0]["celle"].values()))
    assert cella["stato"] == "valido" and cella["obbligatorio"] is False


def test_matrice_ignora_percorsi_disattivati(client, db, formazione, auth, utente, crea_corso, crea_percorso):
    p = crea_percorso([crea_corso("Corso")], [utente])
    p.is_active = False
    db.commit()
    assert client.get("/api/registro/matrice", headers=auth(formazione)).json()["persone"] == []


def test_export_matrice_e_registro(client, formazione, auth, utente, crea_corso, crea_percorso):
    crea_percorso([crea_corso("Corso Export")], [utente])
    for formato, tipo in (("csv", "text/csv"), ("xlsx", "spreadsheetml"), ("pdf", "application/pdf")):
        r = client.get("/api/registro/matrice/export", headers=auth(formazione), params={"formato": formato})
        assert r.status_code == 200 and tipo in r.headers["content-type"]
    assert "Mancante" in client.get("/api/registro/matrice/export", headers=auth(formazione)).text
    assert client.get("/api/registro/matrice/export", headers=auth(formazione), params={"formato": "exe"}).status_code == 400
