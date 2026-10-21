"""2.10.0: percorsi che iscrivono (libero / sequenziale / con propedeuticita'), blocco dei corsi, spostamento delle iscrizioni."""
from datetime import timedelta

import pytest

from app.models.corso import Corso
from app.models.edizione import ModalitaErogazione as M, StatoEdizione as SE
from app.models.iscrizione import Iscrizione, StatoIscrizione as S
from app.models.notification import Notification
from app.models.percorso import PercorsoAssegnazione
from app.models.video import StatoVideo, VideoContenuto
from app.services.percorsi_iscrizioni import avanza_e_invita

from conftest import adesso


@pytest.fixture
def video(db):
    v = VideoContenuto(titolo="Video", stato=StatoVideo.pronto, durata_secondi=100)
    db.add(v); db.commit()
    return v


@pytest.fixture
def mondo(db, crea_corso):
    """Tre corsi A, B, C."""
    return {n: crea_corso(f"Corso {n}") for n in "ABC"}


def percorso(client, auth, formazione, corsi, modalita="libero", richiede=None, nome="Percorso"):
    """Crea un percorso con i corsi nell'ordine dato; `richiede` = {indice_passo: [indici richiesti]} (da 1)."""
    steps = [{"corso_id": str(c.id), "ordine": n, "richiede_step_ordini": (richiede or {}).get(n, [])} for n, c in enumerate(corsi, 1)]
    return client.post("/api/percorsi", headers=auth(formazione), json={"nome": nome, "modalita": modalita, "steps": steps})


def assegna(client, auth, formazione, pid, *persone):
    return client.post(f"/api/percorsi/{pid}/assegna", headers=auth(formazione), json=[str(p.id) for p in persone])


def stati(client, auth, formazione, pid, utente):
    r = client.get(f"/api/percorsi/{pid}/assegnazioni", headers=auth(formazione)).json()
    mio = next(x for x in r if x["user_id"] == str(utente.id))
    return {p["corso_titolo"]: p["stato"] for p in mio["passi"]}


def completa(db, iscrizione):
    iscrizione.stato = S.completato; iscrizione.completato_at = adesso(); db.commit()
    avanza_e_invita(db, user_ids=[iscrizione.user_id])


# --- creazione e controlli ----------------------------------------------------------------------------------------

def test_le_modalita_del_percorso_e_i_controlli(client, auth, formazione, mondo):
    A, B, C = mondo["A"], mondo["B"], mondo["C"]
    for modalita in ("libero", "sequenziale", "propedeuticita"):
        r = percorso(client, auth, formazione, [A, B], modalita=modalita, richiede={2: [1]} if modalita == "propedeuticita" else None, nome=f"P-{modalita}")
        assert r.status_code == 200 and r.json()["modalita"] == modalita
    assert percorso(client, auth, formazione, [A, B], modalita="inventata").status_code == 422
    assert percorso(client, auth, formazione, [A, A]).status_code == 400                                       # un corso una volta sola
    cicli = percorso(client, auth, formazione, [A, B, C], modalita="propedeuticita", richiede={1: [2], 2: [1]}, nome="Giro")
    assert cicli.status_code == 400 and "richiamano" in cicli.json()["detail"]
    assert percorso(client, auth, formazione, [A, B], modalita="propedeuticita", richiede={1: [1]}, nome="Se stesso").status_code == 400
    # in modalita' sequenziale i prerequisiti si ricavano dall'ordine: non se ne scrivono
    seq = percorso(client, auth, formazione, [A, B, C], modalita="sequenziale", richiede={1: [3]}, nome="Seq").json()
    assert all(s["richiede_step_ids"] == [] for s in seq["steps"])


# --- iscrizione ai corsi ------------------------------------------------------------------------------------------

def test_percorso_libero_iscrive_a_tutti_i_corsi_scegliendo_le_sessioni(client, auth, formazione, utente, db, crea_edizione, mondo, video):
    A, B, C = mondo["A"], mondo["B"], mondo["C"]
    sempre = crea_edizione(A, stato=SE.pianificata, modalita=M.video, data_inizio=None, sempre_aperta=True, video_id=video.id)
    lontana = crea_edizione(B, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=30))
    vicina = crea_edizione(B, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=5))
    passata = crea_edizione(C, stato=SE.pianificata, data_inizio=adesso() - timedelta(days=2))            # gia' iniziata: non vale
    pid = percorso(client, auth, formazione, [A, B, C]).json()["id"]
    r = assegna(client, auth, formazione, pid, utente).json()
    assert r["assegnati"] == [str(utente.id)] and r["iscrizioni"] == 2 and r["in_attesa_sessione"] == 1
    db.expire_all()
    mie = {i.edizione_id for i in db.query(Iscrizione).filter(Iscrizione.user_id == utente.id).all()}
    assert mie == {sempre.id, vicina.id}                                                                     # video sempre aperto + la sessione piu' vicina
    assert stati(client, auth, formazione, pid, utente) == {"Corso A": "iscritto", "Corso B": "iscritto", "Corso C": "in_attesa_sessione"}
    testi = [n.testo for n in db.query(Notification).filter(Notification.user_id == utente.id).all()]
    assert any("Ti è stato assegnato il percorso" in t for t in testi) and any("ora puoi iniziare" in t and "Corso A" in t for t in testi)
    assert any("sei stato iscritto" in t and "Corso B" in t for t in testi)
    # riassegnare non cambia niente
    assert assegna(client, auth, formazione, pid, utente).json()["saltati"][0]["motivo"] == "ha già il percorso"


def test_se_la_sessione_e_piena_si_passa_alla_successiva_poi_si_aspetta(client, auth, formazione, utente, crea_utente, db, crea_edizione, crea_iscrizione, mondo):
    B = mondo["B"]
    piena = crea_edizione(B, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=3), posti_max=1)
    crea_iscrizione(piena, crea_utente("altro@t.it"), stato=S.iscritto)
    libera = crea_edizione(B, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=9), posti_max=5)
    pid = percorso(client, auth, formazione, [B]).json()["id"]
    assegna(client, auth, formazione, pid, utente)
    db.expire_all(); assert [i.edizione_id for i in db.query(Iscrizione).filter(Iscrizione.user_id == utente.id)] == [libera.id]
    # nessuna sessione con posti: in attesa
    solo_piena = crea_utente("solo@t.it")
    libera.posti_max = 1; db.commit()
    assegna(client, auth, formazione, pid, solo_piena)
    assert stati(client, auth, formazione, pid, solo_piena) == {"Corso B": "in_attesa_sessione"}


def test_senza_sessione_si_aspetta_e_alla_pubblicazione_si_viene_iscritti(client, auth, formazione, utente, db, crea_edizione, mondo):
    B = mondo["B"]
    pid = percorso(client, auth, formazione, [B]).json()["id"]
    r = assegna(client, auth, formazione, pid, utente).json()
    assert r["iscrizioni"] == 0 and r["in_attesa_sessione"] == 1
    assert stati(client, auth, formazione, pid, utente) == {"Corso B": "in_attesa_sessione"}
    avviso = db.query(Notification).filter(Notification.user_id == formazione.id, Notification.tipo == "percorso_senza_sessione").one()
    assert "Corso B" in avviso.testo and "1 persona aspetta" in avviso.testo
    # la Formazione prepara una sessione (bozza): ancora niente. Pubblicandola, chi aspettava viene iscritto da solo.
    bozza = crea_edizione(B, stato=SE.bozza, data_inizio=adesso() + timedelta(days=10))
    assert db.query(Iscrizione).filter(Iscrizione.user_id == utente.id).count() == 0
    assert client.post(f"/api/edizioni/{bozza.id}/pianifica", headers=auth(formazione)).status_code == 200
    db.expire_all(); assert [i.edizione_id for i in db.query(Iscrizione).filter(Iscrizione.user_id == utente.id)] == [bozza.id]
    assert stati(client, auth, formazione, pid, utente) == {"Corso B": "iscritto"}


def test_iscrizione_progressiva_nel_percorso_sequenziale(client, auth, formazione, utente, db, crea_edizione, mondo, video):
    A, B, C = mondo["A"], mondo["B"], mondo["C"]
    ea = crea_edizione(A, stato=SE.pianificata, modalita=M.video, data_inizio=None, sempre_aperta=True, video_id=video.id)
    eb = crea_edizione(B, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=4))
    ec = crea_edizione(C, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=8))
    pid = percorso(client, auth, formazione, [A, B, C], modalita="sequenziale").json()["id"]
    r = assegna(client, auth, formazione, pid, utente).json()
    assert r["iscrizioni"] == 1                                                                              # solo il primo corso
    assert stati(client, auth, formazione, pid, utente) == {"Corso A": "iscritto", "Corso B": "bloccato", "Corso C": "bloccato"}
    # guardando il video fino in fondo (completamento automatico) si sblocca e si iscrive il secondo
    i = db.query(Iscrizione).filter(Iscrizione.user_id == utente.id).one()
    secondo = 0
    while secondo < 90:
        secondo += 10
        client.post(f"/api/iscrizioni/{i.id}/progresso", headers=auth(utente), json={"secondo_corrente": secondo})
    assert stati(client, auth, formazione, pid, utente) == {"Corso A": "completato", "Corso B": "iscritto", "Corso C": "bloccato"}
    db.expire_all(); assert {x.edizione_id for x in db.query(Iscrizione).filter(Iscrizione.user_id == utente.id)} == {ea.id, eb.id}
    # il secondo si completa (chiusura a mano): si sblocca il terzo
    ib = db.query(Iscrizione).filter(Iscrizione.edizione_id == eb.id).one()
    completa(db, ib)
    assert stati(client, auth, formazione, pid, utente) == {"Corso A": "completato", "Corso B": "completato", "Corso C": "iscritto"}


def test_propedeuticita_scelte_passo_per_passo(client, auth, formazione, utente, db, crea_edizione, mondo):
    A, B, C = mondo["A"], mondo["B"], mondo["C"]
    ea, eb, ec = (crea_edizione(x, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=d)) for x, d in ((A, 3), (B, 4), (C, 9)))
    pid = percorso(client, auth, formazione, [A, B, C], modalita="propedeuticita", richiede={3: [1, 2]}).json()["id"]
    assegna(client, auth, formazione, pid, utente)
    assert stati(client, auth, formazione, pid, utente) == {"Corso A": "iscritto", "Corso B": "iscritto", "Corso C": "bloccato"}
    completa(db, db.query(Iscrizione).filter(Iscrizione.edizione_id == ea.id).one())
    assert stati(client, auth, formazione, pid, utente)["Corso C"] == "bloccato"                              # serve anche B
    completa(db, db.query(Iscrizione).filter(Iscrizione.edizione_id == eb.id).one())
    assert stati(client, auth, formazione, pid, utente)["Corso C"] == "iscritto"


def test_chi_ha_gia_completato_un_corso_lo_ha_fatto(client, auth, formazione, utente, db, crea_edizione, crea_iscrizione, mondo):
    A, B = mondo["A"], mondo["B"]
    crea_iscrizione(crea_edizione(A, stato=SE.chiusa), utente, stato=S.completato)                            # fatto anni fa, fuori da ogni percorso
    crea_edizione(B, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=6))
    pid = percorso(client, auth, formazione, [A, B], modalita="sequenziale").json()["id"]
    r = assegna(client, auth, formazione, pid, utente).json()
    assert r["iscrizioni"] == 1
    assert stati(client, auth, formazione, pid, utente) == {"Corso A": "completato", "Corso B": "iscritto"}


def test_un_corso_non_completato_non_si_riscrive_da_solo(client, auth, formazione, utente, db, crea_edizione, crea_iscrizione, mondo):
    A = mondo["A"]
    crea_iscrizione(crea_edizione(A, stato=SE.chiusa), utente, stato=S.non_completato)
    crea_edizione(A, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=6))
    pid = percorso(client, auth, formazione, [A]).json()["id"]
    r = assegna(client, auth, formazione, pid, utente).json()
    assert r["iscrizioni"] == 0
    assert stati(client, auth, formazione, pid, utente) == {"Corso A": "da_rifare"}                           # decide la Formazione (puo' spostarlo o iscriverlo)


def test_se_la_persona_annulla_non_le_si_riassegna_la_stessa_sessione(client, auth, formazione, utente, db, crea_edizione, mondo):
    from app.services.percorsi_iscrizioni import esegui_percorsi
    B = mondo["B"]
    prima = crea_edizione(B, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=3))
    pid = percorso(client, auth, formazione, [B]).json()["id"]
    assegna(client, auth, formazione, pid, utente)
    i = db.query(Iscrizione).filter(Iscrizione.user_id == utente.id).one()
    assert client.post(f"/api/edizioni/{prima.id}/iscrizioni/{i.id}/annulla", headers=auth(utente)).status_code == 200
    esegui_percorsi(db)
    db.expire_all(); assert db.query(Iscrizione).filter(Iscrizione.user_id == utente.id, Iscrizione.stato != S.annullato).count() == 0
    seconda = crea_edizione(B, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=12))
    riassunto = esegui_percorsi(db)
    db.expire_all(); assert [x.edizione_id for x in db.query(Iscrizione).filter(Iscrizione.user_id == utente.id, Iscrizione.stato != S.annullato)] == [seconda.id]
    assert "iscritti 1" in riassunto


# --- blocco ---------------------------------------------------------------------------------------------------------

def test_un_corso_bloccato_non_si_anticipa(client, auth, formazione, utente, db, crea_edizione, crea_utente, crea_ufficio, mondo):
    A, B = mondo["A"], mondo["B"]
    for c in (A, B):
        c.permetti_autoiscrizione = True; c.iscrizione_responsabili = "diretta"
    db.commit()
    crea_edizione(A, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=3))
    eb = crea_edizione(B, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=9))
    capo = crea_utente("capo@t.it", nome="Capo", cognome="Ufficio")
    crea_ufficio("Produzione", membri=[capo, utente], responsabile=capo)
    pid = percorso(client, auth, formazione, [A, B], modalita="sequenziale").json()["id"]
    assegna(client, auth, formazione, pid, utente)
    # da solo
    r = client.post(f"/api/autoiscrizioni/edizioni/{eb.id}", headers=auth(utente))
    assert r.status_code == 403 and "Prima completa «Corso A»" in r.json()["detail"] and "Percorso" in r.json()["detail"]
    cat = {x["corso_titolo"]: x for x in client.get("/api/catalogo", headers=auth(utente)).json()}
    assert cat["Corso B"]["bloccato"] and "Corso A" in cat["Corso B"]["bloccato"]
    assert "Corso A" in client.get(f"/api/edizioni/{eb.id}", headers=auth(utente)).json()["mio_blocco"]
    # dal responsabile
    r = client.post(f"/api/edizioni/{eb.id}/iscrizioni", headers=auth(capo), json=[str(utente.id)]).json()
    assert r["iscritti"] == [] and "Prima completa" in r["non_iscritti"][0]["motivo"]
    B.iscrizione_responsabili = "su_richiesta"; db.commit()                                                  # richiesta del responsabile (approva la Formazione)
    r = client.post("/api/team/richieste", headers=auth(capo), json={"edizione_id": str(eb.id), "user_ids": [str(utente.id)]})
    assert r.status_code == 200 and r.json()["richieste"] == 0 and "Prima completa" in r.json()["bloccati"][0]["motivo"]
    B.iscrizione_responsabili = "diretta"; db.commit()
    # la Formazione puo' farlo di proposito
    assert client.post(f"/api/edizioni/{eb.id}/iscrizioni", headers=auth(formazione), json=[str(utente.id)]).json()["iscritti"] == [str(utente.id)]
    # un corso fuori dai percorsi della persona non e' bloccato
    altro = crea_utente("altro@t.it")
    assert client.post(f"/api/autoiscrizioni/edizioni/{eb.id}", headers=auth(altro)).status_code == 200


# --- gestione delle assegnazioni ---------------------------------------------------------------------------------

def test_elenco_togli_e_privacy(client, auth, formazione, utente, crea_utente, db, crea_edizione, mondo):
    A = mondo["A"]
    crea_edizione(A, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=3))
    pid = percorso(client, auth, formazione, [A]).json()["id"]
    assegna(client, auth, formazione, pid, utente)
    elenco = client.get(f"/api/percorsi/{pid}/assegnazioni", headers=auth(formazione)).json()
    assert elenco[0]["nome"] == utente.full_name and (elenco[0]["completati"], elenco[0]["totale"]) == (0, 1)
    assert client.get(f"/api/percorsi/{pid}/assegnazioni", headers=auth(utente)).status_code == 403
    assert client.post(f"/api/percorsi/{pid}/assegna", headers=auth(utente), json=[str(utente.id)]).status_code == 403
    # lo stato di una persona non lo vede un collega, ma lei e la Formazione si'
    collega = crea_utente("collega@t.it")
    assert client.get(f"/api/percorsi/{pid}/stato/{utente.id}", headers=auth(collega)).status_code == 403
    assert client.get(f"/api/percorsi/{pid}/stato/{utente.id}", headers=auth(utente)).status_code == 200
    assert client.get(f"/api/percorsi/{pid}/stato/{utente.id}", headers=auth(formazione)).status_code == 200
    # togliere il percorso non annulla le iscrizioni
    assert client.delete(f"/api/percorsi/{pid}/assegnazioni/{utente.id}", headers=auth(formazione)).status_code == 200
    assert client.delete(f"/api/percorsi/{pid}/assegnazioni/{utente.id}", headers=auth(formazione)).status_code == 404
    db.expire_all()
    assert db.query(PercorsoAssegnazione).count() == 0 and db.query(Iscrizione).filter(Iscrizione.user_id == utente.id, Iscrizione.stato == S.iscritto).count() == 1
    # persone non attive o inesistenti sono saltate
    inattivo = crea_utente("fuori@t.it"); inattivo.is_active = False; db.commit()
    r = client.post(f"/api/percorsi/{pid}/assegna", headers=auth(formazione), json=[str(inattivo.id), "00000000-0000-0000-0000-000000000000"]).json()
    assert r["assegnati"] == [] and len(r["saltati"]) == 2


# --- spostare una persona ----------------------------------------------------------------------------------------

def test_la_formazione_sposta_una_persona_su_un_altra_sessione(client, auth, formazione, utente, crea_utente, db, crea_edizione, crea_iscrizione, mondo):
    A, B = mondo["A"], mondo["B"]
    s1 = crea_edizione(A, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=3), posti_max=2)
    s2 = crea_edizione(A, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=15), posti_max=1)
    altro_corso = crea_edizione(B, stato=SE.pianificata, data_inizio=adesso() + timedelta(days=4))
    i = crea_iscrizione(s1, utente)
    url = f"/api/edizioni/{s1.id}/iscrizioni/{i.id}/sposta"
    assert client.post(url, headers=auth(utente), json={"edizione_id": str(s2.id)}).status_code == 403
    assert client.post(url, headers=auth(formazione), json={"edizione_id": str(altro_corso.id)}).status_code == 400          # altro corso
    assert client.post(url, headers=auth(formazione), json={"edizione_id": str(s1.id)}).status_code == 400                  # stessa sessione
    assert client.post(url, headers=auth(formazione), json={"edizione_id": "non-un-id"}).status_code == 404
    # sessione di arrivo piena: non cambia niente
    crea_iscrizione(s2, crea_utente("occupa@t.it"))
    assert client.post(url, headers=auth(formazione), json={"edizione_id": str(s2.id)}).status_code == 400
    db.expire_all(); assert db.get(Iscrizione, i.id).stato == S.iscritto
    s2.posti_max = 3; db.commit()
    r = client.post(url, headers=auth(formazione), json={"edizione_id": str(s2.id)})
    assert r.status_code == 200 and r.json()["edizione_id"] == str(s2.id)
    db.expire_all()
    assert db.get(Iscrizione, i.id).stato == S.annullato
    assert db.query(Iscrizione).filter(Iscrizione.edizione_id == s2.id, Iscrizione.user_id == utente.id, Iscrizione.stato == S.iscritto).count() == 1
    assert db.query(Notification).filter(Notification.user_id == utente.id, Notification.tipo == "iscrizione_spostata").count() == 1
    # non si sposta chi e' gia' nella sessione di arrivo ne' un'iscrizione annullata
    nuovo = db.query(Iscrizione).filter(Iscrizione.edizione_id == s2.id, Iscrizione.user_id == utente.id).one()
    assert client.post(f"/api/edizioni/{s2.id}/iscrizioni/{nuovo.id}/sposta", headers=auth(formazione), json={"edizione_id": str(s1.id)}).status_code == 200
    assert client.post(url, headers=auth(formazione), json={"edizione_id": str(s2.id)}).status_code == 400                  # l'originale e' annullata


def test_la_modalita_viaggia_nella_configurazione(client, auth, admin, formazione, mondo, db):
    percorso(client, auth, formazione, [mondo["A"], mondo["B"]], modalita="sequenziale", nome="Seq")
    percorso(client, auth, formazione, [mondo["A"], mondo["B"]], modalita="propedeuticita", richiede={2: [1]}, nome="Prop")
    export = client.get("/api/admin/configurazione/export", headers=auth(admin)).json()
    assert {p["nome"]: p["modalita"] for p in export["percorsi"]} == {"Seq": "sequenziale", "Prop": "propedeuticita"}
    # un file di prima non conosce la modalita': con prerequisiti scritti diventa «con propedeuticita'», altrimenti libero
    vecchio = {**export, "percorsi": [
        {"nome": "Vecchio 1", "motivo": "policy_interna", "trigger": "manuale", "passi": [{"corso": "Corso A", "ordine": 1, "richiede": []}, {"corso": "Corso B", "ordine": 2, "richiede": ["Corso A"]}]},
        {"nome": "Vecchio 2", "motivo": "policy_interna", "trigger": "manuale", "passi": [{"corso": "Corso A", "ordine": 1, "richiede": []}]}]}
    assert client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": vecchio, "applica": True}).status_code == 200
    elenco = {p["nome"]: p["modalita"] for p in client.get("/api/percorsi", headers=auth(admin)).json()}
    assert elenco["Vecchio 1"] == "propedeuticita" and elenco["Vecchio 2"] == "libero"
