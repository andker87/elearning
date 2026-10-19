"""Etichette dei corsi raggruppate in famiglie, e filtri per gli audit."""
import io
import zipfile

from app.models.corso import Corso
from app.models.etichetta import CorsoEtichetta, Etichetta, EtichettaFamiglia
from app.models.iscrizione import StatoIscrizione as S
from app.services.etichette import converti_categorie_in_tematica


def ids(*etichette):
    return [str(e.id) for e in etichette]


def test_il_sistema_non_crea_nessuna_famiglia_di_etichette(db, crea_corso):
    converti_categorie_in_tematica(db)
    assert db.query(EtichettaFamiglia).count() == 0 and db.query(Etichetta).count() == 0     # ognuno definisce le sue
    crea_corso("Senza categoria")
    converti_categorie_in_tematica(db)
    assert db.query(EtichettaFamiglia).count() == 0


def test_chi_arriva_dal_vecchio_campo_categoria_trova_solo_la_tematica(db, crea_corso):
    vecchio = crea_corso("Antincendio", categoria="  sicurezza   sul lavoro ")
    altro = crea_corso("Excel", categoria="Informatica")
    converti_categorie_in_tematica(db)
    assert [f.nome for f in db.query(EtichettaFamiglia).all()] == ["Tematica"]                # nient'altro: niente norme, ambiti, obblighi preimpostati
    da_corso = lambda c: {e.nome for e in db.query(Etichetta).join(CorsoEtichetta, CorsoEtichetta.etichetta_id == Etichetta.id).filter(CorsoEtichetta.corso_id == c.id)}
    assert da_corso(vecchio) == {"sicurezza sul lavoro"} and da_corso(altro) == {"Informatica"}
    converti_categorie_in_tematica(db)  # una seconda volta non fa nulla
    assert db.query(EtichettaFamiglia).count() == 1 and db.query(Etichetta).count() == 2


def test_corso_con_etichette_e_regole(client, db, formazione, auth, famiglie):
    cyber, trasv, legge, policy = famiglie("Tematica", "Cybersecurity"), famiglie("Ambito", "Trasversale"), famiglie("Obbligo", "Obbligo di legge"), famiglie("Obbligo", "Policy interna")
    r = client.post("/api/corsi", headers=auth(formazione), json={"titolo": "Sicurezza informatica", "etichette": ids(cyber, trasv, legge)})
    assert r.status_code == 200
    c = r.json()
    assert {e["nome"] for e in c["etichette"]} == {"Cybersecurity", "Trasversale", "Obbligo di legge"}
    # "Obbligo" e' a scelta singola
    r = client.put(f"/api/corsi/{c['id']}", headers=auth(formazione), json={"titolo": "Sicurezza informatica", "etichette": ids(legge, policy)})
    assert r.status_code == 400 and "una sola" in r.json()["detail"]
    # senza "etichette" nel corpo non si toccano (es. cambio del solo template)
    r = client.put(f"/api/corsi/{c['id']}", headers=auth(formazione), json={"titolo": "Sicurezza informatica", "validita_mesi": 12})
    assert len(r.json()["etichette"]) == 3
    assert client.post("/api/corsi", headers=auth(formazione), json={"titolo": "X", "etichette": ["00000000-0000-0000-0000-000000000000"]}).status_code == 400


def test_famiglia_obbligatoria(client, db, formazione, auth, famiglie):
    t = db.query(EtichettaFamiglia).filter(EtichettaFamiglia.nome == "Tematica").one()
    t.obbligatoria = True
    db.commit()
    r = client.post("/api/corsi", headers=auth(formazione), json={"titolo": "Senza tematica", "etichette": []})
    assert r.status_code == 400 and "Tematica" in r.json()["detail"]
    db.add(Corso(titolo="Vecchio corso"))
    db.commit()
    elenco = client.get("/api/corsi", headers=auth(formazione)).json()
    assert next(c for c in elenco if c["titolo"] == "Vecchio corso")["etichette_mancanti"] == ["Tematica"]


def test_avviso_trasversale_insieme_a_un_cliente(client, db, formazione, auth, famiglie):
    ambito = db.query(EtichettaFamiglia).filter(EtichettaFamiglia.nome == "Ambito").one()
    cliente = client.post(f"/api/etichette/famiglie/{ambito.id}/etichette", headers=auth(formazione), json={"nome": "Cliente1"}).json()
    c = client.post("/api/corsi", headers=auth(formazione), json={"titolo": "Y", "etichette": [cliente["id"], str(famiglie("Ambito", "Trasversale").id)]}).json()
    assert c["avvisi_etichette"] == ["Ambito: «Trasversale» insieme a Cliente1"]  # avviso, non blocco


def test_gestione_etichette_solo_formazione(client, db, formazione, utente, auth, famiglie):
    tematica = db.query(EtichettaFamiglia).filter(EtichettaFamiglia.nome == "Tematica").one()
    assert client.post(f"/api/etichette/famiglie/{tematica.id}/etichette", headers=auth(utente), json={"nome": "X"}).status_code == 403
    assert client.post("/api/etichette/famiglie", headers=auth(utente), json={"nome": "X"}).status_code == 403
    assert client.get("/api/etichette", headers=auth(utente)).status_code == 200  # leggerle si', per i filtri
    r = client.post(f"/api/etichette/famiglie/{tematica.id}/etichette", headers=auth(formazione), json={"nome": "  cybersecurity "})
    assert r.status_code == 400  # doppione, anche con maiuscole e spazi diversi
    assert client.post("/api/etichette/famiglie", headers=auth(formazione), json={"nome": "Tematica"}).status_code == 400


def test_archiviare_rinominare_eliminare_unire(client, db, formazione, auth, famiglie):
    cyber, privacy = famiglie("Tematica", "Cybersecurity"), famiglie("Tematica", "Privacy e protezione dei dati")
    a = client.post("/api/corsi", headers=auth(formazione), json={"titolo": "A", "etichette": ids(cyber)}).json()
    # in uso: non si elimina, si archivia
    assert client.delete(f"/api/etichette/{cyber.id}", headers=auth(formazione)).status_code == 400
    assert client.put(f"/api/etichette/{cyber.id}", headers=auth(formazione), json={"nome": "Sicurezza informatica", "archiviata": True}).status_code == 200
    assert client.get(f"/api/corsi/{a['id']}", headers=auth(formazione)).json()["etichette"][0]["nome"] == "Sicurezza informatica"  # rinomina ovunque
    assert client.post("/api/corsi", headers=auth(formazione), json={"titolo": "B", "etichette": ids(cyber)}).status_code == 400  # archiviata: non si assegna piu'
    assert client.put(f"/api/corsi/{a['id']}", headers=auth(formazione), json={"titolo": "A", "etichette": ids(cyber)}).status_code == 200  # ma chi l'aveva la tiene
    assert "Sicurezza informatica" not in {e["nome"] for f in client.get("/api/etichette", headers=auth(formazione)).json() for e in f["etichette"]}
    # unire: i corsi passano sull'altra etichetta
    r = client.post(f"/api/etichette/{cyber.id}/unisci", headers=auth(formazione), json={"in_etichetta_id": str(privacy.id)})
    assert r.json() == {"spostati": 1}
    assert client.get(f"/api/corsi/{a['id']}", headers=auth(formazione)).json()["etichette"][0]["nome"] == "Privacy e protezione dei dati"
    ambito = famiglie("Ambito", "Trasversale")
    assert client.post(f"/api/etichette/{privacy.id}/unisci", headers=auth(formazione), json={"in_etichetta_id": str(ambito.id)}).status_code == 400  # famiglie diverse
    nuova = client.post(f"/api/etichette/famiglie/{ambito.famiglia_id}/etichette", headers=auth(formazione), json={"nome": "Cliente2"}).json()
    assert client.delete(f"/api/etichette/{nuova['id']}", headers=auth(formazione)).status_code == 200  # non usata: si elimina


def test_famiglia_a_scelta_singola_solo_se_i_corsi_lo_permettono(client, db, formazione, auth, famiglie):
    t = db.query(EtichettaFamiglia).filter(EtichettaFamiglia.nome == "Tematica").one()
    client.post("/api/corsi", headers=auth(formazione), json={"titolo": "Due temi", "etichette": ids(famiglie("Tematica", "Cybersecurity"), famiglie("Tematica", "Qualità"))})
    r = client.put(f"/api/etichette/famiglie/{t.id}", headers=auth(formazione), json={"nome": "Tematica", "scelta_multipla": False})
    assert r.status_code == 400 and "1 corsi" in r.json()["detail"]


def scenario_audit(db, crea_utente, crea_corso, crea_edizione, crea_iscrizione, famiglie, crea_percorso):
    sic = crea_corso("Antincendio", validita_mesi=60)
    cyb = crea_corso("Phishing", validita_mesi=12)
    db.add_all([CorsoEtichetta(corso_id=sic.id, etichetta_id=famiglie("Riferimento normativo", "D.Lgs 81/08").id),
                CorsoEtichetta(corso_id=sic.id, etichetta_id=famiglie("Ambito", "Trasversale").id),
                CorsoEtichetta(corso_id=cyb.id, etichetta_id=famiglie("Tematica", "Cybersecurity").id),
                CorsoEtichetta(corso_id=cyb.id, etichetta_id=famiglie("Ambito", "Trasversale").id)])
    db.commit()
    u = crea_utente("mario@test.it", full_name="Mario Rossi")
    crea_iscrizione(crea_edizione(sic), u, S.completato, giorni_fa=10)
    crea_iscrizione(crea_edizione(cyb), u, S.completato, giorni_fa=10)
    crea_percorso([sic, cyb], [u])
    return sic, cyb


def test_filtri_per_etichetta_in_registro_matrice_e_pacchetto(client, db, formazione, auth, crea_utente, crea_corso, crea_edizione, crea_iscrizione, famiglie, crea_percorso):
    scenario_audit(db, crea_utente, crea_corso, crea_edizione, crea_iscrizione, famiglie, crea_percorso)
    dlgs = str(famiglie("Riferimento normativo", "D.Lgs 81/08").id)
    trasv = str(famiglie("Ambito", "Trasversale").id)
    cyber = str(famiglie("Tematica", "Cybersecurity").id)
    reg = lambda **p: {r["corso"] for r in client.get("/api/registro", headers=auth(formazione), params=p).json()}
    assert reg() == {"Antincendio", "Phishing"}
    assert reg(etichette=[dlgs]) == {"Antincendio"}
    assert reg(etichette=[trasv]) == {"Antincendio", "Phishing"}
    assert reg(etichette=[trasv, cyber]) == {"Phishing"}             # famiglie diverse: devono valere tutte
    righe = client.get("/api/registro", headers=auth(formazione), params={"etichette": [dlgs]}).json()
    assert "Riferimento normativo: D.Lgs 81/08" in righe[0]["etichette"]
    m = client.get("/api/registro/matrice", headers=auth(formazione), params={"etichette": [dlgs]}).json()
    assert [c["titolo"] for c in m["corsi"]] == ["Antincendio"]
    z = zipfile.ZipFile(io.BytesIO(client.get("/api/registro/pacchetto-ispezione", headers=auth(formazione), params={"etichette": [dlgs]}).content))
    leggimi = z.read(next(n for n in z.namelist() if n.endswith("LEGGIMI.txt"))).decode()
    assert "Riferimento normativo: D.Lgs 81/08" in leggimi
    assert "Etichette" in client.get("/api/registro/export", headers=auth(formazione), params={"etichette": [dlgs]}).text


def test_stessa_famiglia_vale_l_una_o_l_altra(client, db, formazione, auth, crea_corso, famiglie):
    from app.services.etichette import corsi_con_etichette
    ambito = db.query(EtichettaFamiglia).filter(EtichettaFamiglia.nome == "Ambito").one()
    c1 = client.post(f"/api/etichette/famiglie/{ambito.id}/etichette", headers=auth(formazione), json={"nome": "Cliente1"}).json()["id"]
    c2 = client.post(f"/api/etichette/famiglie/{ambito.id}/etichette", headers=auth(formazione), json={"nome": "Cliente2"}).json()["id"]
    a = client.post("/api/corsi", headers=auth(formazione), json={"titolo": "Per cliente 1", "etichette": [c1]}).json()["id"]
    b = client.post("/api/corsi", headers=auth(formazione), json={"titolo": "Per cliente 2", "etichette": [c2]}).json()["id"]
    assert {str(x) for x in corsi_con_etichette(db, [c1, c2])} == {a, b}


def test_etichette_nella_configurazione(client, db, admin, auth, famiglie, crea_corso):
    c = crea_corso("Antincendio")
    db.add(CorsoEtichetta(corso_id=c.id, etichetta_id=famiglie("Riferimento normativo", "D.Lgs 81/08").id))
    db.commit()
    file = client.get("/api/admin/configurazione/export", headers=auth(admin)).json()
    assert {f["famiglia"] for f in file["etichette"]} == {"Tematica", "Riferimento normativo", "Ambito", "Obbligo"}
    assert file["corsi"][0]["etichette"] == [{"famiglia": "Riferimento normativo", "nome": "D.Lgs 81/08"}]
    db.query(CorsoEtichetta).delete(); db.query(Corso).delete(); db.query(Etichetta).delete(); db.query(EtichettaFamiglia).delete()
    db.commit()
    r = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": file, "applica": True}).json()
    assert len(r["sezioni"]["etichette"]["creati"]) == 4 and r["sezioni"]["corsi"]["creati"] == ["Antincendio"]
    nuovo = db.query(Corso).one()
    assert [e.nome for e in db.query(Etichetta).join(CorsoEtichetta, CorsoEtichetta.etichetta_id == Etichetta.id).filter(CorsoEtichetta.corso_id == nuovo.id)] == ["D.Lgs 81/08"]
    again = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": file, "applica": True}).json()
    assert again["totali"] == {"creati": 0, "aggiornati": 0}


def test_filtri_per_etichetta_in_kpi_dashboard_e_sessioni(client, db, formazione, auth, crea_utente, crea_corso, crea_edizione, crea_iscrizione, famiglie, crea_percorso):
    from datetime import timedelta
    from conftest import adesso
    from app.models.edizione import StatoEdizione
    sic, cyb = scenario_audit(db, crea_utente, crea_corso, crea_edizione, crea_iscrizione, famiglie, crea_percorso)
    dlgs = str(famiglie("Riferimento normativo", "D.Lgs 81/08").id)
    cyber = str(famiglie("Tematica", "Cybersecurity").id)
    # KPI per corso
    kpi = lambda **p: {r["corso_titolo"] for r in client.get("/api/dashboard/kpi/per-corso", headers=auth(formazione), params=p).json()}
    assert kpi() == {"Antincendio", "Phishing"} and kpi(etichette=[dlgs]) == {"Antincendio"} and kpi(etichette=[cyber]) == {"Phishing"}
    r = client.get("/api/dashboard/kpi/riepilogo", headers=auth(formazione), params={"etichette": [dlgs]})
    assert r.status_code == 200
    assert client.get("/api/dashboard/kpi/per-docente", headers=auth(formazione), params={"etichette": [dlgs]}).status_code == 200
    assert client.get("/api/dashboard/kpi/andamento", headers=auth(formazione), params={"etichette": [dlgs]}).status_code == 200
    assert client.get("/api/dashboard/kpi/export", headers=auth(formazione), params={"vista": "per-corso", "etichette": [dlgs]}).text.count("Antincendio") == 1
    # Dashboard Ufficio Formazione: persone con problemi (corsi scaduti) e scoperture
    vecchio = crea_corso("Antiriciclaggio", validita_mesi=12)
    db.add(CorsoEtichetta(corso_id=vecchio.id, etichetta_id=famiglie("Tematica", "Qualità").id))
    db.commit()
    crea_iscrizione(crea_edizione(vecchio), crea_utente("lento@test.it", full_name="Lento"), S.completato, giorni_fa=500)
    problemi = lambda **p: {pr["corso_titolo"] for x in client.get("/api/dashboard/formazione/persone", headers=auth(formazione), params=p).json() for pr in x["problemi"]}
    assert problemi() == {"Antiriciclaggio"} and problemi(etichette=[dlgs]) == set()
    assert client.get("/api/dashboard/formazione/kpi", headers=auth(formazione), params={"etichette": [dlgs]}).json()["n_scaduti"] == 0
    assert client.get("/api/dashboard/formazione/kpi", headers=auth(formazione)).json()["n_scaduti"] == 1
    # sessioni: catalogo e sessioni imminenti
    crea_edizione(sic, stato=StatoEdizione.pianificata, data_inizio=adesso() + timedelta(days=5))
    crea_edizione(cyb, stato=StatoEdizione.pianificata, data_inizio=adesso() + timedelta(days=6))
    elenco = lambda **p: {e["corso_titolo"] for e in client.get("/api/edizioni", headers=auth(formazione), params=p).json() if e["stato"] == "pianificata"}
    assert elenco() == {"Antincendio", "Phishing"} and elenco(etichette=[cyber]) == {"Phishing"}
    ed = next(e for e in client.get("/api/edizioni", headers=auth(formazione)).json() if e["corso_titolo"] == "Antincendio")
    assert {x["nome"] for x in ed["corso_etichette"]} == {"D.Lgs 81/08", "Trasversale"}
    imminenti = client.get("/api/dashboard/formazione/sessioni-imminenti", headers=auth(formazione), params={"etichette": [dlgs]}).json()
    assert [s["corso_titolo"] for s in imminenti] == ["Antincendio"]
