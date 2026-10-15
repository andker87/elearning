"""Fusione di richieste di fabbisogno simili con tracciabilita' completa."""
from app.models.audit import AuditLog
from app.models.notification import Notification


def albero(db, crea_utente, crea_ufficio):
    """Direzione > Divisione > (Acquisti, Legale, Compliance): 3 livelli, un responsabile per ufficio."""
    resp = {n: crea_utente(f"{n.lower()}@test.it", full_name=f"Resp {n}") for n in ("Direzione", "Divisione", "Acquisti", "Legale", "Compliance")}
    uff = {"Direzione": crea_ufficio("Direzione", responsabile=resp["Direzione"])}
    uff["Divisione"] = crea_ufficio("Divisione", responsabile=resp["Divisione"])
    uff["Divisione"].parent_id = uff["Direzione"].id
    for n in ("Acquisti", "Legale", "Compliance"):
        uff[n] = crea_ufficio(n, responsabile=resp[n])
        uff[n].parent_id = uff["Divisione"].id
    db.commit()
    return uff, resp


def spontanea(client, auth, resp, ufficio, argomento, persone=None, note=None, **extra):
    r = client.post("/api/fabbisogno/richieste", headers=auth(resp), json={"ufficio_id": str(ufficio.id), "righe": [
        {"argomento": argomento, "numero_persone_stimate": persone, "note": note, **extra}]})
    assert r.status_code == 200, r.text
    return r.json()[0]


def unisci(client, auth, resp, ids, **corpo):
    return client.post("/api/fabbisogno/richieste/unisci", headers=auth(resp), json={"ids": ids, "argomento": "Privacy GDPR", **corpo})


def tre_richieste(client, auth, uff, resp):
    return [spontanea(client, auth, resp["Acquisti"], uff["Acquisti"], "Privacy GDPR", 10, "per tutti"),
            spontanea(client, auth, resp["Legale"], uff["Legale"], "GDPR e privacy", 6),
            spontanea(client, auth, resp["Compliance"], uff["Compliance"], "privacy", 4, "solo nuovi")]


def test_unione_prosegue_al_posto_delle_originali(client, db, auth, crea_utente, crea_ufficio):
    uff, resp = albero(db, crea_utente, crea_ufficio)
    ids = [r["id"] for r in tre_richieste(client, auth, uff, resp)]
    r = unisci(client, auth, resp["Divisione"], ids)
    assert r.status_code == 200
    u = r.json()
    assert u["numero_persone_stimate"] == 20 and u["e_unione"] and u["n_origini"] == 3
    assert u["uffici_origine"] == ["Acquisti", "Compliance", "Legale"]
    assert u["ufficio_origine_nome"] == "Divisione" and u["ufficio_in_revisione_presso_nome"] == "Direzione"
    # in valutazione presso il livello sopra c'e' solo l'unione
    da_rev = client.get("/api/fabbisogno/richieste/da-revisionare", headers=auth(resp["Direzione"])).json()
    assert [x["id"] for x in da_rev] == [u["id"]]
    assert client.get("/api/fabbisogno/richieste/da-revisionare", headers=auth(resp["Divisione"])).json() == []


def test_persone_modificabili_ma_di_default_la_somma(client, db, auth, crea_utente, crea_ufficio):
    uff, resp = albero(db, crea_utente, crea_ufficio)
    ids = [r["id"] for r in tre_richieste(client, auth, uff, resp)]
    u = unisci(client, auth, resp["Divisione"], ids, numero_persone_stimate=15, note="alcuni si sovrappongono").json()
    assert u["numero_persone_stimate"] == 15 and u["note"] == "alcuni si sovrappongono"


def test_regole_di_validazione(client, db, auth, formazione, crea_utente, crea_ufficio):
    uff, resp = albero(db, crea_utente, crea_ufficio)
    a, b, c = tre_richieste(client, auth, uff, resp)
    assert unisci(client, auth, resp["Divisione"], [a["id"]]).status_code == 400                   # ne servono due
    assert unisci(client, auth, resp["Divisione"], [a["id"], b["id"]], argomento="  ").status_code == 400
    assert unisci(client, auth, resp["Direzione"], [a["id"], b["id"]]).status_code == 403            # non sono in attesa da lui
    assert unisci(client, auth, resp["Acquisti"], [a["id"], b["id"]]).status_code == 403             # non e' il revisore
    altra = spontanea(client, auth, resp["Divisione"], uff["Divisione"], "Altro tema")             # in attesa presso Direzione
    assert unisci(client, auth, resp["Divisione"], [a["id"], altra["id"]]).status_code == 403        # una e' in attesa piu' in alto
    assert unisci(client, auth, resp["Divisione"], [a["id"], "non-un-id"]).status_code in (400, 404)


def test_campagne_diverse_non_si_uniscono(client, db, auth, formazione, crea_utente, crea_ufficio):
    uff, resp = albero(db, crea_utente, crea_ufficio)
    spont = spontanea(client, auth, resp["Acquisti"], uff["Acquisti"], "Privacy", 3)
    client.post("/api/fabbisogno/campagne", headers=auth(formazione), json={"titolo": "2027"})
    invito = client.get("/api/fabbisogno/inviti/miei", headers=auth(resp["Direzione"])).json()[0]["inviti"][0]
    client.post(f"/api/fabbisogno/inviti/{invito['id']}/delega", headers=auth(resp["Direzione"]))
    inv2 = client.get("/api/fabbisogno/inviti/miei", headers=auth(resp["Divisione"])).json()[0]["inviti"][0]
    client.post(f"/api/fabbisogno/inviti/{inv2['id']}/delega", headers=auth(resp["Divisione"]))
    inv3 = client.get("/api/fabbisogno/inviti/miei", headers=auth(resp["Legale"])).json()[0]["inviti"][0]
    di_campagna = client.post(f"/api/fabbisogno/inviti/{inv3['id']}/rispondi", headers=auth(resp["Legale"]), json={"righe": [{"argomento": "Privacy"}]}).json()[0]
    r = unisci(client, auth, resp["Divisione"], [spont["id"], di_campagna["id"]])
    assert r.status_code == 400 and "campagne diverse" in r.json()["detail"]


def test_chi_ha_scritto_le_originali_le_vede_unite_e_viene_avvisato(client, db, auth, crea_utente, crea_ufficio):
    uff, resp = albero(db, crea_utente, crea_ufficio)
    a, b, c = tre_richieste(client, auth, uff, resp)
    u = unisci(client, auth, resp["Divisione"], [a["id"], b["id"], c["id"]]).json()
    mie = client.get("/api/fabbisogno/richieste/mie", headers=auth(resp["Legale"])).json()
    mia = next(x for x in mie if x["id"] == b["id"])
    assert mia["stato"] == "fusa" and mia["unita_in"]["argomento"] == "Privacy GDPR" and mia["unita_in"]["ufficio_nome"] == "Divisione"
    assert mia["stato_effettivo"] == "in_revisione" and mia["presso_effettivo_nome"] == "Direzione"
    assert db.query(Notification).filter(Notification.user_id == resp["Legale"].id, Notification.tipo == "fabbisogno_unione").count() == 1
    assert db.query(Notification).filter(Notification.user_id == resp["Divisione"].id, Notification.tipo == "fabbisogno_unione").count() == 0


def test_lo_stato_dell_unione_si_riflette_sulle_originali(client, db, auth, crea_utente, crea_ufficio):
    uff, resp = albero(db, crea_utente, crea_ufficio)
    a, b, c = tre_richieste(client, auth, uff, resp)
    u = unisci(client, auth, resp["Divisione"], [a["id"], b["id"]]).json()
    client.put(f"/api/fabbisogno/richieste/{u['id']}/rifiuta", headers=auth(resp["Direzione"]), json={"motivo": "gia' coperto da un corso"})
    mia = next(x for x in client.get("/api/fabbisogno/richieste/mie", headers=auth(resp["Acquisti"])).json() if x["id"] == a["id"])
    assert mia["stato_effettivo"] == "rifiutata" and mia["motivo_rifiuto_effettivo"] == "gia' coperto da un corso"
    assert c["id"] != a["id"]  # la terza non era nell'unione e resta com'era
    ancora = next(x for x in client.get("/api/fabbisogno/richieste/mie", headers=auth(resp["Compliance"])).json() if x["id"] == c["id"])
    assert ancora["stato_effettivo"] == "in_revisione"


def test_albero_di_provenienza_su_piu_livelli(client, db, auth, formazione, crea_utente, crea_ufficio):
    uff, resp = albero(db, crea_utente, crea_ufficio)
    a, b, c = tre_richieste(client, auth, uff, resp)
    u1 = unisci(client, auth, resp["Divisione"], [a["id"], b["id"]], argomento="Privacy").json()
    extra = spontanea(client, auth, resp["Divisione"], uff["Divisione"], "Privacy dei dati", 5)
    # la Divisione unisce di nuovo: l'unione precedente + una richiesta sua, in attesa presso Direzione
    u2 = unisci(client, auth, resp["Direzione"], [u1["id"], extra["id"]], argomento="Privacy e dati").json()
    assert u2["n_origini"] == 3 and u2["uffici_origine"] == ["Acquisti", "Divisione", "Legale"] and u2["numero_persone_stimate"] == 21
    t = client.get(f"/api/fabbisogno/richieste/{u2['id']}/origine", headers=auth(formazione)).json()
    assert t["argomento"] == "Privacy e dati" and {f["argomento"] for f in t["figli"]} == {"Privacy", "Privacy dei dati"}
    interna = next(f for f in t["figli"] if f["argomento"] == "Privacy")
    assert interna["e_unione"] and {x["ufficio_nome"] for x in interna["figli"]} == {"Acquisti", "Legale"}
    foglia = next(x for x in interna["figli"] if x["ufficio_nome"] == "Acquisti")
    assert foglia["numero_persone_stimate"] == 10 and foglia["note"] == "per tutti" and foglia["creata_da_nome"] == "Resp Acquisti"
    # chi ha scritto una originale la vede, un estraneo no
    assert client.get(f"/api/fabbisogno/richieste/{u2['id']}/origine", headers=auth(resp["Legale"])).status_code == 200
    assert client.get(f"/api/fabbisogno/richieste/{u2['id']}/origine", headers=auth(resp["Compliance"])).status_code == 403


def test_la_formazione_vede_solo_l_unione_con_i_numeri_giusti(client, db, auth, formazione, crea_utente, crea_ufficio):
    uff, resp = albero(db, crea_utente, crea_ufficio)
    a, b, c = tre_richieste(client, auth, uff, resp)
    u = unisci(client, auth, resp["Divisione"], [a["id"], b["id"], c["id"]]).json()
    client.put(f"/api/fabbisogno/richieste/{u['id']}/approva", headers=auth(resp["Direzione"]))
    vista = client.get("/api/fabbisogno/richieste-formative", headers=auth(formazione), params={"stato": "tutte"}).json()
    assert vista["riepilogo"] == {"richieste": 1, "argomenti": 1, "uffici": 3, "persone": 20, "richieste_originali": 3}
    gruppo = vista["items"][0]
    assert gruppo["richieste"] == 1 and gruppo["richieste_originali"] == 3 and gruppo["uffici"] == ["Acquisti", "Compliance", "Legale"]
    # il filtro per ufficio guarda le richieste originali: filtrando "Legale" l'unione compare ancora
    f = client.get("/api/fabbisogno/richieste-formative", headers=auth(formazione), params={"vista": "elenco", "ufficio_id": str(uff["Legale"].id)}).json()
    assert [x["id"] for x in f["items"]] == [u["id"]]
    csv_ = client.get("/api/fabbisogno/richieste-formative/export", headers=auth(formazione)).text
    assert "Acquisti, Compliance, Legale" in csv_ and "Richieste originali" in csv_


def test_scomposizione_solo_finche_nessuno_sopra_l_ha_valutata(client, db, auth, crea_utente, crea_ufficio):
    uff, resp = albero(db, crea_utente, crea_ufficio)
    a, b, c = tre_richieste(client, auth, uff, resp)
    u = unisci(client, auth, resp["Divisione"], [a["id"], b["id"]]).json()
    assert client.post(f"/api/fabbisogno/richieste/{u['id']}/scomponi", headers=auth(resp["Direzione"])).status_code == 403
    assert client.post(f"/api/fabbisogno/richieste/{a['id']}/scomponi", headers=auth(resp["Divisione"])).status_code == 400   # non e' un'unione
    assert client.post(f"/api/fabbisogno/richieste/{u['id']}/scomponi", headers=auth(resp["Divisione"])).status_code == 200
    da_rev = client.get("/api/fabbisogno/richieste/da-revisionare", headers=auth(resp["Divisione"])).json()
    assert {x["id"] for x in da_rev} == {a["id"], b["id"], c["id"]}  # tornano tutte da valutare, intatte
    u2 = unisci(client, auth, resp["Divisione"], [a["id"], b["id"]]).json()
    client.put(f"/api/fabbisogno/richieste/{u2['id']}/approva", headers=auth(resp["Direzione"]))
    r = client.post(f"/api/fabbisogno/richieste/{u2['id']}/scomponi", headers=auth(resp["Divisione"]))
    assert r.status_code == 400 and "già stata valutata" in r.json()["detail"]


def test_approva_e_rifiuta_in_blocco_tutto_o_niente(client, db, auth, crea_utente, crea_ufficio):
    uff, resp = albero(db, crea_utente, crea_ufficio)
    a, b, c = tre_richieste(client, auth, uff, resp)
    altra = spontanea(client, auth, resp["Divisione"], uff["Divisione"], "Altro")  # non e' sua da valutare
    r = client.put("/api/fabbisogno/richieste/approva-multiple", headers=auth(resp["Divisione"]), json={"ids": [a["id"], altra["id"]]})
    assert r.status_code == 403
    assert {x["id"] for x in client.get("/api/fabbisogno/richieste/da-revisionare", headers=auth(resp["Divisione"])).json()} == {a["id"], b["id"], c["id"]}
    assert client.put("/api/fabbisogno/richieste/approva-multiple", headers=auth(resp["Divisione"]), json={"ids": [a["id"], b["id"]]}).json() == {"approvate": 2}
    assert client.put("/api/fabbisogno/richieste/rifiuta-multiple", headers=auth(resp["Divisione"]), json={"ids": [c["id"]], "motivo": "fuori budget"}).json() == {"rifiutate": 1}
    mia = next(x for x in client.get("/api/fabbisogno/richieste/mie", headers=auth(resp["Compliance"])).json() if x["id"] == c["id"])
    assert mia["stato"] == "rifiutata" and mia["motivo_rifiuto"] == "fuori budget"
    assert client.put("/api/fabbisogno/richieste/approva-multiple", headers=auth(resp["Divisione"]), json={"ids": []}).status_code == 400


def test_unione_e_scomposizione_nell_audit(client, db, auth, crea_utente, crea_ufficio):
    uff, resp = albero(db, crea_utente, crea_ufficio)
    a, b, c = tre_richieste(client, auth, uff, resp)
    u = unisci(client, auth, resp["Divisione"], [a["id"], b["id"]]).json()
    client.post(f"/api/fabbisogno/richieste/{u['id']}/scomponi", headers=auth(resp["Divisione"]))
    azioni = [r.action for r in db.query(AuditLog).filter(AuditLog.action.like("FABBISOGNO_%")).order_by(AuditLog.created_at).all()]
    assert azioni == ["FABBISOGNO_UNIONE", "FABBISOGNO_SCOMPOSIZIONE"]
    unione = db.query(AuditLog).filter(AuditLog.action == "FABBISOGNO_UNIONE").one()
    assert "Privacy GDPR (10)" in unione.detail and "Divisione" in unione.detail


def test_chi_guida_due_uffici_non_unisce_richieste_in_attesa_presso_uffici_diversi(client, db, auth, crea_utente, crea_ufficio):
    capo = crea_utente("capo@test.it")
    p1, p2 = crea_ufficio("Area 1", responsabile=capo), crea_ufficio("Area 2", responsabile=capo)
    r1, r2 = crea_utente("r1@test.it"), crea_utente("r2@test.it")
    c1, c2 = crea_ufficio("Team 1", responsabile=r1), crea_ufficio("Team 2", responsabile=r2)
    c1.parent_id, c2.parent_id = p1.id, p2.id
    db.commit()
    a = spontanea(client, auth, r1, c1, "Privacy", 2)
    b = spontanea(client, auth, r2, c2, "Privacy", 3)
    r = unisci(client, auth, capo, [a["id"], b["id"]])
    assert r.status_code == 400 and "stesso ufficio" in r.json()["detail"]
