"""2.6.0: «Il mio team» e corsi chiusi/aperti ai responsabili."""
from datetime import timedelta

import pytest

from app.models.edizione import StatoEdizione as SE
from app.models.group import Group
from app.models.iscrizione import Iscrizione, StatoIscrizione as S
from app.models.notification import Notification
from app.models.richiesta_iscrizione import RichiestaIscrizione

from conftest import adesso


@pytest.fixture
def team(db, crea_utente, crea_ufficio):
    """Produzione (capo) con Anna e Bruno; sottoufficio Linea 2 (Carla responsabile) con Dario; Vendite e' di un altro."""
    capo = crea_utente("capo@t.it", nome="Capo", cognome="Reparto")
    anna, bruno = crea_utente("anna@t.it", nome="Anna", cognome="Verdi"), crea_utente("bruno@t.it", nome="Bruno", cognome="Neri")
    carla, dario = crea_utente("carla@t.it", nome="Carla", cognome="Gialli"), crea_utente("dario@t.it", nome="Dario", cognome="Blu")
    altro, estraneo = crea_utente("altro@t.it", nome="Altro", cognome="Capo"), crea_utente("x@t.it", nome="Xavier", cognome="Estraneo")
    prod = crea_ufficio("Produzione", membri=[capo, anna, bruno], responsabile=capo)
    linea = Group(name="Linea 2", parent_id=prod.id, is_ufficio=True, responsabile_id=carla.id)
    db.add(linea); db.commit()
    from app.models.group import UserGroup
    db.add_all([UserGroup(user_id=carla.id, group_id=linea.id), UserGroup(user_id=dario.id, group_id=linea.id)]); db.commit()
    crea_ufficio("Vendite", membri=[altro, estraneo], responsabile=altro)
    return dict(capo=capo, anna=anna, bruno=bruno, carla=carla, dario=dario, altro=altro, estraneo=estraneo)


def sessione(crea_corso, crea_edizione, db, modo="diretta", titolo="Corso", stato=SE.pianificata, **kw):
    c = crea_corso(titolo); c.iscrizione_responsabili = modo; db.commit()
    return crea_edizione(c, stato=stato, **kw)


# --- accesso e organigramma ----------------------------------------------------------------------

def test_solo_i_responsabili_vedono_il_team(client, auth, utente, team):
    for url in ("/api/team/organigramma", "/api/team/sessioni", "/api/team/corsi-disponibili", "/api/team/richieste"):
        assert client.get(url, headers=auth(utente)).status_code == 403
    assert client.post("/api/team/richieste", headers=auth(utente), json={"edizione_id": "x", "user_ids": []}).status_code == 403


def test_l_organigramma_e_solo_il_mio_ramo(client, auth, team, db):
    r = client.get("/api/team/organigramma", headers=auth(team["capo"])).json()
    assert [u["name"] for u in r["uffici"]] == ["Produzione"] and r["uffici"][0]["e_mio"] is True
    assert {p["full_name"] for p in r["uffici"][0]["persone"]} == {"Capo Reparto", "Anna Verdi", "Bruno Neri"}
    linea = r["uffici"][0]["figli"][0]
    assert linea["name"] == "Linea 2" and linea["responsabile"]["nome"] == "Carla Gialli" and linea["e_mio"] is False
    assert {p["full_name"] for p in linea["persone"]} == {"Carla Gialli", "Dario Blu"}
    assert r["totale_persone"] == 5
    assert "Xavier Estraneo" not in str(r)                                    # l'altro ufficio non si vede
    # la responsabile del sottoufficio vede solo il suo
    c = client.get("/api/team/organigramma", headers=auth(team["carla"])).json()
    assert [u["name"] for u in c["uffici"]] == ["Linea 2"] and c["totale_persone"] == 2


# --- sessioni del team ---------------------------------------------------------------------------

def test_le_sessioni_del_team_sono_solo_quelle_con_le_mie_persone(client, auth, team, db, crea_corso, crea_edizione, crea_iscrizione):
    mia = sessione(crea_corso, crea_edizione, db, titolo="Con Anna")
    altra = sessione(crea_corso, crea_edizione, db, titolo="Senza nessuno")
    solo_estraneo = sessione(crea_corso, crea_edizione, db, titolo="Solo estraneo")
    chiusa = sessione(crea_corso, crea_edizione, db, titolo="Chiusa con Bruno", stato=SE.chiusa)
    crea_iscrizione(mia, team["anna"], stato=S.iscritto); crea_iscrizione(mia, team["estraneo"], stato=S.iscritto)
    crea_iscrizione(solo_estraneo, team["estraneo"], stato=S.iscritto)
    crea_iscrizione(chiusa, team["bruno"], stato=S.completato)
    crea_iscrizione(altra, team["dario"], stato=S.annullato)
    r = client.get("/api/team/sessioni", headers=auth(team["capo"])).json()
    assert [s["corso_titolo"] for s in r] == ["Con Anna"]
    assert [p["nome"] for p in r[0]["persone"]] == ["Anna Verdi"]            # di chi e' del mio team, non l'estraneo
    assert "durata_effettiva_minuti" in r[0] and "luogo" in r[0]
    tutte = client.get("/api/team/sessioni?concluse=true", headers=auth(team["capo"])).json()
    assert {s["corso_titolo"] for s in tutte} == {"Con Anna", "Chiusa con Bruno"}


def test_un_admin_che_guida_un_ufficio_vede_solo_il_suo_team(client, auth, admin, db, crea_ufficio, crea_utente, crea_corso, crea_edizione, crea_iscrizione):
    mio = crea_utente("mio@t.it")
    crea_ufficio("Uff", membri=[mio], responsabile=admin)
    fuori = crea_utente("fuori@t.it")
    s1, s2 = sessione(crea_corso, crea_edizione, db, titolo="Del mio"), sessione(crea_corso, crea_edizione, db, titolo="Di altri")
    crea_iscrizione(s1, mio, stato=S.iscritto); crea_iscrizione(s2, fuori, stato=S.iscritto)
    assert [s["corso_titolo"] for s in client.get("/api/team/sessioni", headers=auth(admin)).json()] == ["Del mio"]


# --- corsi chiusi e aperti -------------------------------------------------------------------------

def test_il_corso_nuovo_e_chiuso_e_il_modo_si_controlla(client, auth, formazione):
    c = client.post("/api/corsi", headers=auth(formazione), json={"titolo": "Nuovo"})
    assert c.status_code == 200 and c.json()["iscrizione_responsabili"] == "solo_formazione"
    cid = c.json()["id"]
    r = client.put(f"/api/corsi/{cid}", headers=auth(formazione), json={"titolo": "Nuovo", "iscrizione_responsabili": "su_richiesta"})
    assert r.status_code == 200 and r.json()["iscrizione_responsabili"] == "su_richiesta"
    assert client.put(f"/api/corsi/{cid}", headers=auth(formazione), json={"titolo": "Nuovo", "iscrizione_responsabili": "boh"}).status_code == 422


def test_un_responsabile_iscrive_direttamente_solo_se_il_corso_lo_permette(client, auth, team, formazione, db, crea_corso, crea_edizione):
    ids = [str(team["anna"].id)]
    for modo, atteso in (("diretta", 200), ("solo_formazione", 403), ("su_richiesta", 403)):
        s = sessione(crea_corso, crea_edizione, db, modo=modo, titolo=f"C-{modo}")
        r = client.post(f"/api/edizioni/{s.id}/iscrizioni", headers=auth(team["capo"]), json=ids)
        assert r.status_code == atteso, (modo, r.text)
        # la Formazione iscrive sempre, qualunque sia il modo
        assert client.post(f"/api/edizioni/{s.id}/iscrizioni", headers=auth(formazione), json=[str(team["bruno"].id)]).status_code == 200
    s = sessione(crea_corso, crea_edizione, db, modo="diretta", titolo="Altro")
    assert client.post(f"/api/edizioni/{s.id}/iscrizioni", headers=auth(team["capo"]), json=[str(team["estraneo"].id)]).status_code == 403


def test_i_corsi_disponibili_sono_solo_quelli_aperti_e_futuri(client, auth, team, db, crea_corso, crea_edizione, crea_iscrizione):
    dir_ = sessione(crea_corso, crea_edizione, db, modo="diretta", titolo="Diretta", data_inizio=adesso() + timedelta(days=5), posti_max=4)
    ric = sessione(crea_corso, crea_edizione, db, modo="su_richiesta", titolo="Su richiesta", data_inizio=adesso() + timedelta(days=9))
    sessione(crea_corso, crea_edizione, db, modo="solo_formazione", titolo="Chiuso", data_inizio=adesso() + timedelta(days=5))
    sessione(crea_corso, crea_edizione, db, modo="diretta", titolo="Bozza", stato=SE.bozza, data_inizio=adesso() + timedelta(days=5))
    sessione(crea_corso, crea_edizione, db, modo="diretta", titolo="Finita", stato=SE.chiusa)
    sessione(crea_corso, crea_edizione, db, modo="diretta", titolo="Passata", data_inizio=adesso() - timedelta(days=5), data_fine=adesso() - timedelta(days=4))
    crea_iscrizione(dir_, team["anna"], stato=S.iscritto)
    db.add(RichiestaIscrizione(edizione_id=ric.id, user_id=team["bruno"].id, richiedente_id=team["capo"].id)); db.commit()
    r = client.get("/api/team/corsi-disponibili", headers=auth(team["capo"])).json()
    assert [s["corso_titolo"] for s in r["sessioni"]] == ["Diretta", "Su richiesta"]       # per data
    d, q = r["sessioni"]
    assert d["modo"] == "diretta" and d["posti_liberi"] == 3 and d["persone_stato"] == {str(team["anna"].id): "iscritto"}
    assert q["modo"] == "su_richiesta" and q["persone_stato"] == {str(team["bruno"].id): "richiesta_in_attesa"}
    assert {p["nome"] for p in r["team"]} == {"Anna Verdi", "Bruno Neri", "Carla Gialli", "Dario Blu"}      # le mie persone (non io)


# --- richieste ----------------------------------------------------------------------------------

def chiedi(client, auth, capo, s, *persone):
    return client.post("/api/team/richieste", headers=auth(capo), json={"edizione_id": str(s.id), "user_ids": [str(p.id) for p in persone]})


def test_la_richiesta_arriva_alla_formazione(client, auth, team, formazione, admin, db, crea_corso, crea_edizione, crea_iscrizione):
    s = sessione(crea_corso, crea_edizione, db, modo="su_richiesta", titolo="Antincendio", data_inizio=adesso() + timedelta(days=7))
    crea_iscrizione(s, team["dario"], stato=S.iscritto)
    r = chiedi(client, auth, team["capo"], s, team["anna"], team["bruno"], team["dario"])
    assert r.status_code == 200 and r.json()["richieste"] == 2 and r.json()["gia_iscritti"] == ["Dario Blu"]
    assert chiedi(client, auth, team["capo"], s, team["anna"]).json() == {"richieste": 0, "gia_iscritti": [], "gia_richiesti": ["Anna Verdi"], "bloccati": []}   # una sola richiesta in attesa
    avvisi = db.query(Notification).filter(Notification.tipo == "richiesta_iscrizione").all()
    assert {n.user_id for n in avvisi} == {formazione.id, admin.id} and all("Antincendio" in n.testo and n.link == "/richieste-iscrizione" for n in avvisi)
    elenco = client.get("/api/richieste-iscrizione", headers=auth(formazione)).json()
    assert {x["persona"] for x in elenco["in_attesa"]} == {"Anna Verdi", "Bruno Neri"}
    assert elenco["in_attesa"][0]["richiedente"] == "Capo Reparto" and elenco["in_attesa"][0]["ufficio"] == "Produzione" and elenco["in_attesa"][0]["corso_titolo"] == "Antincendio"
    mie = client.get("/api/team/richieste", headers=auth(team["capo"])).json()
    assert {x["persona"] for x in mie} == {"Anna Verdi", "Bruno Neri"} and all(x["stato"] == "in_attesa" for x in mie)


def test_chi_puo_chiedere_e_per_chi(client, auth, team, db, crea_corso, crea_edizione):
    ric = sessione(crea_corso, crea_edizione, db, modo="su_richiesta", titolo="R")
    assert chiedi(client, auth, team["capo"], ric, team["estraneo"]).status_code == 403            # non e' del mio team
    assert client.post("/api/team/richieste", headers=auth(team["capo"]), json={"edizione_id": str(ric.id), "user_ids": []}).status_code == 400
    for modo in ("diretta", "solo_formazione"):
        s = sessione(crea_corso, crea_edizione, db, modo=modo, titolo=modo)
        assert chiedi(client, auth, team["capo"], s, team["anna"]).status_code == 400              # a questi corsi non si chiede
    chiusa = sessione(crea_corso, crea_edizione, db, modo="su_richiesta", titolo="chiusa", stato=SE.chiusa)
    assert chiedi(client, auth, team["capo"], chiusa, team["anna"]).status_code == 400
    bozza = sessione(crea_corso, crea_edizione, db, modo="su_richiesta", titolo="bozza", stato=SE.bozza)
    assert chiedi(client, auth, team["capo"], bozza, team["anna"]).status_code == 400


def test_la_formazione_approva_e_la_persona_viene_iscritta(client, auth, team, formazione, db, crea_corso, crea_edizione):
    s = sessione(crea_corso, crea_edizione, db, modo="su_richiesta", titolo="Primo soccorso", data_inizio=adesso() + timedelta(days=3))
    chiedi(client, auth, team["capo"], s, team["anna"])
    rid = client.get("/api/richieste-iscrizione", headers=auth(formazione)).json()["in_attesa"][0]["id"]
    assert client.put(f"/api/richieste-iscrizione/{rid}/approva", headers=auth(team["capo"])).status_code == 403     # solo la Formazione
    assert client.put(f"/api/richieste-iscrizione/{rid}/approva", headers=auth(formazione)).status_code == 200
    db.expire_all()
    assert db.query(Iscrizione).filter(Iscrizione.edizione_id == s.id, Iscrizione.user_id == team["anna"].id).one().stato == S.iscritto
    esito = db.query(Notification).filter(Notification.user_id == team["capo"].id, Notification.tipo == "richiesta_iscrizione_esito").one()
    assert "approvata" in esito.testo and "Anna Verdi" in esito.testo and "confermata" in esito.testo
    assert client.put(f"/api/richieste-iscrizione/{rid}/approva", headers=auth(formazione)).status_code == 400    # gia' gestita
    elenco = client.get("/api/richieste-iscrizione", headers=auth(formazione)).json()
    assert elenco["in_attesa"] == [] and elenco["gestite"][0]["stato"] == "approvata"
    assert client.get("/api/team/richieste", headers=auth(team["capo"])).json()[0]["stato"] == "approvata"


def test_il_rifiuto_dice_perche(client, auth, team, formazione, db, crea_corso, crea_edizione):
    s = sessione(crea_corso, crea_edizione, db, modo="su_richiesta", titolo="Corso X")
    chiedi(client, auth, team["capo"], s, team["bruno"])
    rid = client.get("/api/richieste-iscrizione", headers=auth(formazione)).json()["in_attesa"][0]["id"]
    assert client.put(f"/api/richieste-iscrizione/{rid}/rifiuta", headers=auth(formazione), json={"motivo": "posti riservati"}).status_code == 200
    assert db.query(Iscrizione).filter(Iscrizione.user_id == team["bruno"].id).count() == 0
    n = db.query(Notification).filter(Notification.user_id == team["capo"].id, Notification.tipo == "richiesta_iscrizione_esito").one()
    assert "rifiutata" in n.testo and "posti riservati" in n.testo
    r = client.get("/api/team/richieste", headers=auth(team["capo"])).json()[0]
    assert r["stato"] == "rifiutata" and r["motivo_rifiuto"] == "posti riservati"
    chiedi(client, auth, team["capo"], s, team["bruno"])                       # dopo un rifiuto si puo' richiedere di nuovo
    assert client.get("/api/richieste-iscrizione", headers=auth(formazione)).json()["in_attesa"][0]["persona"] == "Bruno Neri"


def test_se_non_ci_sono_posti_la_richiesta_resta_in_attesa_o_va_in_lista(client, auth, team, formazione, db, crea_corso, crea_edizione, crea_iscrizione, crea_utente):
    pieno = sessione(crea_corso, crea_edizione, db, modo="su_richiesta", titolo="Pieno", posti_max=1)
    crea_iscrizione(pieno, crea_utente("altro1@t.it"), stato=S.iscritto)
    chiedi(client, auth, team["capo"], pieno, team["anna"])
    rid = client.get("/api/richieste-iscrizione", headers=auth(formazione)).json()["in_attesa"][0]["id"]
    r = client.put(f"/api/richieste-iscrizione/{rid}/approva", headers=auth(formazione))
    assert r.status_code == 400 and "esauriti" in r.json()["detail"]
    assert client.get("/api/richieste-iscrizione", headers=auth(formazione)).json()["in_attesa"][0]["posti_liberi"] == 0     # resta in attesa
    pieno.lista_attesa_abilitata = True; db.commit()
    assert client.put(f"/api/richieste-iscrizione/{rid}/approva", headers=auth(formazione)).status_code == 200
    db.expire_all()
    assert db.query(Iscrizione).filter(Iscrizione.user_id == team["anna"].id).one().stato == S.in_lista_attesa


def test_la_situazione_formativa_di_una_persona_del_team(client, auth, team, db, crea_corso, crea_edizione, crea_iscrizione):
    c = crea_corso("Antincendio", validita_mesi=12)
    fatta = crea_edizione(c, stato=SE.chiusa)
    i = crea_iscrizione(fatta, team["anna"], stato=S.completato, giorni_fa=350)
    prossima = sessione(crea_corso, crea_edizione, db, titolo="Prossima", data_inizio=adesso() + timedelta(days=9))
    crea_iscrizione(prossima, team["anna"], stato=S.iscritto)
    r = client.get(f"/api/team/persone/{team['anna'].id}/formazione", headers=auth(team["capo"])).json()
    per_corso = {x["corso_titolo"]: x for x in r["iscrizioni"]}
    assert per_corso["Antincendio"]["in_scadenza"] is True and per_corso["Antincendio"]["scaduto"] is False and per_corso["Antincendio"]["scadenza"]
    assert per_corso["Prossima"]["stato"] == "iscritto" and r["persona"]["full_name"] == "Anna Verdi"
    assert client.get(f"/api/team/persone/{team['estraneo'].id}/formazione", headers=auth(team["capo"])).status_code == 403
    assert client.get(f"/api/team/persone/{team['capo'].id}/formazione", headers=auth(team["capo"])).status_code == 403     # se stessi non e' «il team»


def test_l_esportazione_della_configurazione_porta_il_modo_di_iscrizione(client, auth, admin, formazione):
    client.post("/api/corsi", headers=auth(formazione), json={"titolo": "Aperto", "iscrizione_responsabili": "diretta"})
    dati = client.get("/api/admin/configurazione/export", headers=auth(admin)).json()
    assert [c["iscrizione_responsabili"] for c in dati["corsi"]] == ["diretta"]


# --- correzioni dalla review della PR #29 --------------------------------------------------------

def test_un_modo_sconosciuto_lascia_il_corso_chiuso(client, auth, team, db, crea_corso, crea_edizione):
    s = sessione(crea_corso, crea_edizione, db, modo="refuso", titolo="Strano")
    r = client.post(f"/api/edizioni/{s.id}/iscrizioni", headers=auth(team["capo"]), json=[str(team["anna"].id)])
    assert r.status_code == 403 and "Formazione" in r.json()["detail"]


def test_l_importazione_scarta_un_modo_di_iscrizione_sconosciuto(client, auth, admin, db):
    from app.models.corso import Corso
    file = client.get("/api/admin/configurazione/export", headers=auth(admin)).json()      # intestazione vera, poi i corsi di prova
    file["corsi"] = [{"titolo": "Importato", "iscrizione_responsabili": "refuso"}, {"titolo": "Aperto", "iscrizione_responsabili": "diretta"}]
    r = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": file, "applica": True})
    assert r.status_code == 200, r.text
    db.expire_all()
    modi = {c.titolo: c.iscrizione_responsabili for c in db.query(Corso).all()}
    assert modi == {"Importato": "solo_formazione", "Aperto": "diretta"}      # il refuso non apre il corso


def test_non_si_chiede_ne_si_approva_per_una_sessione_gia_finita(client, auth, team, formazione, db, crea_corso, crea_edizione):
    passata = sessione(crea_corso, crea_edizione, db, modo="su_richiesta", titolo="Passata", data_inizio=adesso() - timedelta(days=5), data_fine=adesso() - timedelta(days=4))
    assert chiedi(client, auth, team["capo"], passata, team["anna"]).status_code == 400
    # richiesta fatta quando la sessione era ancora futura, poi la data passa
    s = sessione(crea_corso, crea_edizione, db, modo="su_richiesta", titolo="Scade", data_inizio=adesso() + timedelta(days=2), data_fine=adesso() + timedelta(days=3))
    assert chiedi(client, auth, team["capo"], s, team["anna"]).status_code == 200
    s.data_inizio, s.data_fine = adesso() - timedelta(days=2), adesso() - timedelta(days=1); db.commit()
    rid = client.get("/api/richieste-iscrizione", headers=auth(formazione)).json()["in_attesa"][0]["id"]
    r = client.put(f"/api/richieste-iscrizione/{rid}/approva", headers=auth(formazione))
    assert r.status_code == 400 and "rifiuta" in r.json()["detail"]
    assert db.query(Iscrizione).filter(Iscrizione.edizione_id == s.id).count() == 0


def test_non_si_approva_per_una_persona_disattivata(client, auth, team, formazione, db, crea_corso, crea_edizione):
    s = sessione(crea_corso, crea_edizione, db, modo="su_richiesta", titolo="Corso", data_inizio=adesso() + timedelta(days=3))
    chiedi(client, auth, team["capo"], s, team["anna"])
    team["anna"].is_active = False; db.commit()
    rid = client.get("/api/richieste-iscrizione", headers=auth(formazione)).json()["in_attesa"][0]["id"]
    r = client.put(f"/api/richieste-iscrizione/{rid}/approva", headers=auth(formazione))
    assert r.status_code == 400 and "non è più attiva" in r.json()["detail"]
    assert db.query(Iscrizione).filter(Iscrizione.edizione_id == s.id).count() == 0
    assert client.put(f"/api/richieste-iscrizione/{rid}/rifiuta", headers=auth(formazione), json={"motivo": "Persona non più attiva"}).status_code == 200    # si puo' rifiutare
