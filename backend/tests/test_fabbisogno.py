"""Fabbisogno formativo: campagna dall'alto, delega a cascata, richiesta spontanea."""
from app.models.fabbisogno import FabbisognoCampagnaInvito, StatoInvito


def nuova_campagna(client, formazione, auth):
    return client.post("/api/fabbisogno/campagne", headers=auth(formazione), json={"titolo": "2027"}).json()


def test_la_campagna_invita_gli_uffici_di_primo_livello(client, db, formazione, auth, crea_utente, crea_ufficio):
    resp = crea_utente("resp@test.it")
    crea_ufficio("Ufficio A", responsabile=resp)
    nuova_campagna(client, formazione, auth)
    inviti = client.get("/api/fabbisogno/inviti/miei", headers=auth(resp)).json()
    assert [i["ufficio_nome"] for i in inviti[0]["inviti"]] == ["Ufficio A"]


def test_ufficio_creato_dopo_l_avvio_riceve_comunque_l_invito(client, db, formazione, auth, crea_utente, crea_ufficio):
    nuova_campagna(client, formazione, auth)  # nessun ufficio esiste ancora
    resp = crea_utente("resp@test.it")
    crea_ufficio("Compliance", responsabile=resp)
    assert [i["ufficio_nome"] for c in client.get("/api/fabbisogno/inviti/miei", headers=auth(resp)).json() for i in c["inviti"]] == ["Compliance"]
    client.get("/api/fabbisogno/inviti/miei", headers=auth(resp))  # nessun doppione
    assert db.query(FabbisognoCampagnaInvito).count() == 1


def test_campagna_chiusa_non_invita_nessuno(client, formazione, auth, crea_utente, crea_ufficio):
    c = nuova_campagna(client, formazione, auth)
    client.put(f"/api/fabbisogno/campagne/{c['id']}/chiudi", headers=auth(formazione))
    resp = crea_utente("resp@test.it")
    crea_ufficio("Tardivo", responsabile=resp)
    assert client.get("/api/fabbisogno/inviti/miei", headers=auth(resp)).json() == []


def test_chi_non_e_responsabile_non_riceve_inviti(client, formazione, auth, utente, crea_ufficio):
    crea_ufficio("Ufficio A")
    nuova_campagna(client, formazione, auth)
    assert client.get("/api/fabbisogno/inviti/miei", headers=auth(utente)).json() == []


def test_risposta_di_un_ufficio_radice_arriva_a_hr(client, formazione, auth, crea_utente, crea_ufficio):
    resp = crea_utente("resp@test.it")
    crea_ufficio("Ufficio A", responsabile=resp)
    nuova_campagna(client, formazione, auth)
    invito = client.get("/api/fabbisogno/inviti/miei", headers=auth(resp)).json()[0]["inviti"][0]
    r = client.post(f"/api/fabbisogno/inviti/{invito['id']}/rispondi", headers=auth(resp), json={"righe": [{"argomento": "Privacy avanzata", "numero_persone_stimate": 4}]})
    assert r.status_code == 200 and r.json()[0]["stato"] == "approvata_hr"
    coda = client.get("/api/fabbisogno/richieste", headers=auth(formazione)).json()
    assert [x["argomento"] for x in coda] == ["Privacy avanzata"]
    gestito = client.get("/api/fabbisogno/inviti/miei", headers=auth(resp)).json()[0]["inviti"][0]
    assert gestito["stato"] == "risposto" and gestito["risposte"] == 1  # resta visibile, con l'esito


def test_delega_e_risalita_con_approvazione(client, db, formazione, auth, crea_utente, crea_ufficio):
    capo, sotto = crea_utente("capo@test.it"), crea_utente("sotto@test.it")
    padre = crea_ufficio("Direzione", responsabile=capo)
    figlio = crea_ufficio("Compliance", responsabile=sotto)
    figlio.parent_id = padre.id
    db.commit()
    nuova_campagna(client, formazione, auth)
    inv = client.get("/api/fabbisogno/inviti/miei", headers=auth(capo)).json()[0]["inviti"]
    assert [i["ufficio_nome"] for i in inv] == ["Direzione"] and inv[0]["sotto_uffici"] == ["Compliance"]  # il sotto-ufficio non e' invitato direttamente
    assert client.post(f"/api/fabbisogno/inviti/{inv[0]['id']}/delega", headers=auth(capo)).status_code == 200
    assert client.get("/api/fabbisogno/inviti/miei", headers=auth(capo)).json()[0]["inviti"][0]["stato"] == "delegato"
    inv2 = client.get("/api/fabbisogno/inviti/miei", headers=auth(sotto)).json()[0]["inviti"]
    assert [i["ufficio_nome"] for i in inv2] == ["Compliance"]
    r = client.post(f"/api/fabbisogno/inviti/{inv2[0]['id']}/rispondi", headers=auth(sotto), json={"righe": [{"argomento": "Antiriciclaggio"}]})
    assert r.json()[0]["stato"] == "in_revisione"
    da_rev = client.get("/api/fabbisogno/richieste/da-revisionare", headers=auth(capo)).json()
    assert len(da_rev) == 1
    assert client.put(f"/api/fabbisogno/richieste/{da_rev[0]['id']}/approva", headers=auth(capo), json={}).json()["stato"] == "approvata_hr"


def test_richiesta_spontanea_solo_per_i_responsabili(client, auth, utente, crea_utente, crea_ufficio):
    ufficio = crea_ufficio("Ufficio A")
    assert client.post("/api/fabbisogno/richieste", headers=auth(utente), json={"righe": [{"argomento": "X"}], "ufficio_id": str(ufficio.id)}).status_code == 403
    resp = crea_utente("resp@test.it")
    mio = crea_ufficio("Mio ufficio", responsabile=resp)
    r = client.post("/api/fabbisogno/richieste", headers=auth(resp), json={"righe": [{"argomento": "Excel avanzato"}], "ufficio_id": str(mio.id)})
    assert r.status_code == 200 and r.json()[0]["campagna_id"] is None and r.json()[0]["stato"] == "approvata_hr"
    assert client.post("/api/fabbisogno/richieste", headers=auth(resp), json={"righe": [{"argomento": "X"}], "ufficio_id": str(ufficio.id)}).status_code == 403  # non e' il suo ufficio


def test_piu_righe_in_una_sola_risposta_e_righe_vuote_scartate(client, formazione, auth, crea_utente, crea_ufficio):
    resp = crea_utente("resp@test.it")
    crea_ufficio("Ufficio A", responsabile=resp)
    nuova_campagna(client, formazione, auth)
    invito = client.get("/api/fabbisogno/inviti/miei", headers=auth(resp)).json()[0]["inviti"][0]
    righe = [{"argomento": "Privacy", "numero_persone_stimate": 3, "note": "entro l'estate"}, {"argomento": "   "}, {"argomento": "Sicurezza"}]
    r = client.post(f"/api/fabbisogno/inviti/{invito['id']}/rispondi", headers=auth(resp), json={"righe": righe})
    assert [x["argomento"] for x in r.json()] == ["Privacy", "Sicurezza"] and r.json()[0]["note"] == "entro l'estate"
    assert {x["argomento"] for x in client.get("/api/fabbisogno/richieste", headers=auth(formazione)).json()} == {"Privacy", "Sicurezza"}
    # un invito si risponde una volta sola
    assert client.post(f"/api/fabbisogno/inviti/{invito['id']}/rispondi", headers=auth(resp), json={"righe": righe}).status_code == 400


def test_risposta_senza_argomenti_rifiutata(client, formazione, auth, crea_utente, crea_ufficio):
    resp = crea_utente("resp@test.it")
    crea_ufficio("Ufficio A", responsabile=resp)
    nuova_campagna(client, formazione, auth)
    invito = client.get("/api/fabbisogno/inviti/miei", headers=auth(resp)).json()[0]["inviti"][0]
    assert client.post(f"/api/fabbisogno/inviti/{invito['id']}/rispondi", headers=auth(resp), json={"righe": [{"argomento": " "}]}).status_code == 400
    assert client.post(f"/api/fabbisogno/inviti/{invito['id']}/rispondi", headers=auth(resp), json={"righe": []}).status_code == 400


def test_chi_guida_due_uffici_vede_la_campagna_una_volta(client, formazione, auth, crea_utente, crea_ufficio):
    resp = crea_utente("resp@test.it")
    crea_ufficio("Ufficio A", responsabile=resp)
    crea_ufficio("Ufficio B", responsabile=resp)
    nuova_campagna(client, formazione, auth)
    campagne = client.get("/api/fabbisogno/inviti/miei", headers=auth(resp)).json()
    assert len(campagne) == 1 and {i["ufficio_nome"] for i in campagne[0]["inviti"]} == {"Ufficio A", "Ufficio B"}


# --- vista della Formazione: filtri, ordinamento, raggruppamento ----------------------------

def scenario_richieste(client, formazione, auth, crea_utente, crea_ufficio):
    """Tre uffici di primo livello rispondono alla campagna; uno apre anche una richiesta spontanea."""
    uffici = {}
    for nome in ("Compliance", "Acquisti", "Legale"):
        resp = crea_utente(f"{nome.lower()}@test.it", full_name=f"Resp {nome}")
        uffici[nome] = (crea_ufficio(nome, responsabile=resp), resp)
    nuova_campagna(client, formazione, auth)
    dati = {"Compliance": [{"argomento": "Privacy GDPR", "numero_persone_stimate": 10, "periodo": "trimestre", "riferimento_periodo": "Q1 2027"},
                           {"argomento": "Antiriciclaggio", "numero_persone_stimate": 4}],
            "Acquisti": [{"argomento": "  privacy   gdpr ", "numero_persone_stimate": 6}],
            "Legale": [{"argomento": "Contratti", "numero_persone_stimate": 2, "note": "solo neoassunti"}]}
    for nome, righe in dati.items():
        resp = uffici[nome][1]
        invito = client.get("/api/fabbisogno/inviti/miei", headers=auth(resp)).json()[0]["inviti"][0]
        assert client.post(f"/api/fabbisogno/inviti/{invito['id']}/rispondi", headers=auth(resp), json={"righe": righe}).status_code == 200
    client.post("/api/fabbisogno/richieste", headers=auth(uffici["Legale"][1]),
                json={"righe": [{"argomento": "Excel avanzato", "numero_persone_stimate": 8}], "ufficio_id": str(uffici["Legale"][0].id)})
    return uffici


def test_vista_raggruppata_unisce_le_varianti_dello_stesso_argomento(client, formazione, auth, crea_utente, crea_ufficio):
    scenario_richieste(client, formazione, auth, crea_utente, crea_ufficio)
    r = client.get("/api/fabbisogno/richieste-formative", headers=auth(formazione)).json()
    per_argomento = {g["argomento"].lower(): g for g in r["items"]}
    privacy = next(g for k, g in per_argomento.items() if "privacy" in k)
    assert privacy["richieste"] == 2 and privacy["persone"] == 16 and privacy["n_uffici"] == 2 and privacy["uffici"] == ["Acquisti", "Compliance"]
    assert r["riepilogo"] == {"richieste": 5, "argomenti": 4, "uffici": 3, "persone": 30, "richieste_originali": 5}
    assert r["items"][0]["persone"] == 16  # ordinati per persone, dal piu' richiesto


def test_filtri_della_vista(client, formazione, auth, crea_utente, crea_ufficio):
    uffici = scenario_richieste(client, formazione, auth, crea_utente, crea_ufficio)
    def cerca(**p):
        return client.get("/api/fabbisogno/richieste-formative", headers=auth(formazione), params={"vista": "elenco", **p}).json()
    assert cerca()["totale"] == 5
    assert cerca(campagna_id="spontanee")["totale"] == 1
    assert cerca(ufficio_id=str(uffici["Compliance"][0].id))["totale"] == 2
    assert cerca(q="neoassunti")["totale"] == 1                      # cerca anche nelle note
    assert cerca(periodo="trimestre")["totale"] == 1
    assert cerca(argomento="PRIVACY GDPR")["totale"] == 2            # confronto senza maiuscole e spazi doppi
    assert cerca(stato="in_revisione")["totale"] == 0 and cerca(stato="tutte")["totale"] == 5
    assert client.get("/api/fabbisogno/richieste-formative", headers=auth(formazione), params={"stato": "boh"}).status_code == 400


def test_filtro_ufficio_comprende_i_sotto_uffici(client, db, formazione, auth, crea_utente, crea_ufficio):
    capo, sotto = crea_utente("capo@test.it"), crea_utente("sotto@test.it")
    padre, figlio = crea_ufficio("Direzione", responsabile=capo), crea_ufficio("Figlio", responsabile=sotto)
    figlio.parent_id = padre.id
    db.commit()
    client.post("/api/fabbisogno/richieste", headers=auth(sotto), json={"righe": [{"argomento": "X"}], "ufficio_id": str(figlio.id)})
    r = client.get("/api/fabbisogno/richieste-formative", headers=auth(formazione),
                   params={"vista": "elenco", "ufficio_id": str(padre.id), "stato": "tutte"}).json()
    assert r["totale"] == 1


def test_ordinamento_e_paginazione_dell_elenco(client, formazione, auth, crea_utente, crea_ufficio):
    scenario_richieste(client, formazione, auth, crea_utente, crea_ufficio)
    def pagina(**p):
        return client.get("/api/fabbisogno/richieste-formative", headers=auth(formazione), params={"vista": "elenco", **p}).json()
    assert [r["numero_persone_stimate"] for r in pagina(ordine="persone", direzione="desc")["items"]] == [10, 8, 6, 4, 2]
    assert [r["numero_persone_stimate"] for r in pagina(ordine="persone", direzione="asc")["items"]] == [2, 4, 6, 8, 10]
    assert [r["ufficio_origine_nome"] for r in pagina(ordine="ufficio", direzione="asc")["items"]][0] == "Acquisti"
    p2 = pagina(ordine="persone", direzione="desc", per_pagina=2, pagina=2)
    assert p2["totale"] == 5 and [r["numero_persone_stimate"] for r in p2["items"]] == [6, 4]


def test_vista_riservata_alla_formazione_e_export(client, formazione, utente, auth, crea_utente, crea_ufficio):
    assert client.get("/api/fabbisogno/richieste-formative", headers=auth(utente)).status_code == 403
    assert client.get("/api/fabbisogno/richieste-formative/export", headers=auth(utente)).status_code == 403
    scenario_richieste(client, formazione, auth, crea_utente, crea_ufficio)
    csv_ = client.get("/api/fabbisogno/richieste-formative/export", headers=auth(formazione), params={"campagna_id": "spontanee"}).text
    assert "Excel avanzato" in csv_ and "Contratti" not in csv_
    assert client.get("/api/fabbisogno/richieste-formative/export", headers=auth(formazione), params={"formato": "xlsx"}).status_code == 200


def test_campagne_con_i_numeri_di_avanzamento(client, formazione, auth, crea_utente, crea_ufficio):
    scenario_richieste(client, formazione, auth, crea_utente, crea_ufficio)
    c = client.get("/api/fabbisogno/campagne", headers=auth(formazione)).json()[0]
    assert (c["inviti_risposti"], c["inviti_da_decidere"], c["inviti_delegati"], c["richieste"]) == (3, 0, 0, 4)
