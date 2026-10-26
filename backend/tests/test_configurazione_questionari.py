"""2.12.3: questionari di gradimento e copertine dentro la configurazione esportabile."""
import base64
import io
import os

import pytest
from PIL import Image

from app.models.corso import Corso
from app.models.questionario import DomandaGradimento, QuestionarioGradimento
from app.services import cifratura
from app.services import copertine as copertine_svc


@pytest.fixture(autouse=True)
def cartella(tmp_path, monkeypatch):
    monkeypatch.setattr(copertine_svc, "CARTELLA", str(tmp_path / "copertine"))


def jpeg(larghezza=1280, altezza=720, colore=(30, 120, 90)):
    buf = io.BytesIO(); Image.new("RGB", (larghezza, altezza), colore).save(buf, "JPEG", quality=85); return buf.getvalue()


def png_storto():
    buf = io.BytesIO(); Image.new("RGB", (1000, 1000), (200, 10, 10)).save(buf, "PNG"); return buf.getvalue()


def prepara_dati(db, crea_corso):
    q = QuestionarioGradimento(nome="Aula", is_default=False)
    q.domande.append(DomandaGradimento(testo="Il ritmo era giusto?", tipo="si_no", obbligatoria=True, ordine=0))
    q.domande.append(DomandaGradimento(testo="Quale parte ti e' servita?", tipo="scelta", opzioni=["Teoria", "Esercizi"], ordine=1))
    base = QuestionarioGradimento(nome="Generale", is_default=True)
    base.domande.append(DomandaGradimento(testo="Consiglieresti il corso?", tipo="stelle", ordine=0))
    db.add_all([q, base]); db.commit()
    c = crea_corso("Excel"); c.questionario_gradimento_id = q.id; db.commit()
    return c


def svuota(db):
    from sqlalchemy import text
    db.execute(text("UPDATE corsi SET questionario_gradimento_id = NULL"))
    for t in ("domande_gradimento", "questionari_gradimento", "corsi"):
        db.execute(text(f"DELETE FROM {t}"))
    db.commit()


def test_i_questionari_e_la_scelta_del_corso_viaggiano_nel_file(client, db, admin, auth, crea_corso):
    prepara_dati(db, crea_corso)
    dati = client.get("/api/admin/configurazione/export", headers=auth(admin)).json()
    nomi = {q["nome"]: q for q in dati["questionari"]}
    assert nomi["Generale"]["predefinito"] is True and nomi["Aula"]["predefinito"] is False
    assert [d["testo"] for d in nomi["Aula"]["domande"]] == ["Il ritmo era giusto?", "Quale parte ti e' servita?"]
    assert nomi["Aula"]["domande"][1]["opzioni"] == ["Teoria", "Esercizi"]
    assert dati["corsi"][0]["questionario"] == "Aula"
    # in un ambiente vuoto: anteprima senza scrivere, poi applicazione
    svuota(db)
    anteprima = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": dati, "applica": False}).json()
    assert sorted(anteprima["sezioni"]["questionari"]["creati"]) == ["Aula", "Generale"] and db.query(QuestionarioGradimento).count() == 0
    r = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": dati, "applica": True})
    assert r.status_code == 200, r.text
    db.expire_all()
    aula = db.query(QuestionarioGradimento).filter_by(nome="Aula").one()
    assert [d.tipo for d in aula.domande] == ["si_no", "scelta"] and aula.domande[0].obbligatoria is True
    assert db.query(QuestionarioGradimento).filter_by(is_default=True).one().nome == "Generale"
    assert db.query(Corso).one().questionario_gradimento_id == aula.id
    # un secondo giro con lo stesso file non cambia niente
    ancora = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": dati, "applica": False}).json()
    assert ancora["totali"] == {"creati": 0, "aggiornati": 0}


def test_un_questionario_esistente_riceve_le_domande_nuove_senza_perdere_le_sue(client, db, admin, auth, crea_corso):
    prepara_dati(db, crea_corso)
    dati = client.get("/api/admin/configurazione/export", headers=auth(admin)).json()
    aula = db.query(QuestionarioGradimento).filter_by(nome="Aula").one()
    db.add(DomandaGradimento(questionario_id=aula.id, testo="Solo qui", tipo="testo", ordine=2)); db.commit()
    for q in dati["questionari"]:
        if q["nome"] == "Aula":
            q["domande"].append({"testo": "Domanda dal file", "tipo": "testo", "opzioni": None, "obbligatoria": False, "ordine": 2})
        if q["nome"] == "Generale":
            q["predefinito"] = False
        else:
            q["predefinito"] = True            # il file vuole un altro predefinito: qui ce n'e' gia' uno, non cambia
    r = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": dati, "applica": True}).json()
    assert r["sezioni"]["questionari"]["aggiornati"][0]["campi"] == ["domanda «Domanda dal file»", "ordine"]
    assert any("predefinito" in a for a in r["avvisi"])
    db.expire_all()
    assert {d.testo for d in db.query(QuestionarioGradimento).filter_by(nome="Aula").one().domande} == {"Il ritmo era giusto?", "Quale parte ti e' servita?", "Solo qui", "Domanda dal file"}
    assert db.query(QuestionarioGradimento).filter_by(is_default=True).one().nome == "Generale"


def test_un_questionario_non_valido_e_un_avviso_non_un_errore(client, db, admin, auth):
    dati = {"formato": "elearning-configurazione", "schema": 3, "questionari": [
        {"nome": "Rotto", "domande": [{"testo": "Scegli", "tipo": "scelta", "opzioni": ["una sola"]}]},
        {"nome": "Buono", "domande": [{"testo": "Ok?", "tipo": "si_no"}]}]}
    r = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": dati, "applica": True}).json()
    assert r["sezioni"]["questionari"]["creati"] == ["Buono"] and any("Rotto" in a for a in r["avvisi"])


def test_le_copertine_viaggiano_e_importare_due_volte_non_le_ricomprime(client, db, admin, auth, crea_corso, formazione):
    c = crea_corso("Excel")
    r = client.post(f"/api/corsi/{c.id}/copertina", headers=auth(formazione), files={"file": ("c.png", png_storto(), "image/png")})
    assert r.status_code == 200, r.text
    db.expire_all(); c = db.get(Corso, c.id); v1, p1 = c.copertina_v, c.copertina_path
    dati = client.get("/api/admin/configurazione/export", headers=auth(admin)).json()
    cop = dati["corsi"][0]["copertina"]
    assert cop["v"] == v1 and base64.b64decode(cop["jpeg_base64"]) == cifratura.leggi_file(p1)
    # senza copertine il file e' leggero
    assert "copertina" not in client.get("/api/admin/configurazione/export?copertine=false", headers=auth(admin)).json()["corsi"][0]
    # stesso file sullo stesso ambiente: nessuna differenza; in un ambiente senza copertina: si crea e il codice resta lo stesso
    assert client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": dati, "applica": False}).json()["totali"]["aggiornati"] == 0
    client.delete(f"/api/corsi/{c.id}/copertina", headers=auth(formazione))
    anteprima = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": dati, "applica": False}).json()
    assert anteprima["sezioni"]["corsi"]["aggiornati"][0]["campi"] == ["copertina"]
    db.expire_all()
    assert db.get(Corso, c.id).copertina_path is None
    assert not os.path.isdir(copertine_svc.CARTELLA) or not os.listdir(copertine_svc.CARTELLA)
    assert client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": dati, "applica": True}).status_code == 200
    db.expire_all(); c = db.get(Corso, c.id)
    assert c.copertina_v == v1 and cifratura.leggi_file(c.copertina_path) == base64.b64decode(cop["jpeg_base64"])


def test_una_copertina_rotta_nel_file_e_un_avviso(client, db, admin, auth, crea_corso):
    crea_corso("Excel")
    dati = client.get("/api/admin/configurazione/export", headers=auth(admin)).json()
    dati["corsi"][0]["copertina"] = {"v": "x", "jpeg_base64": base64.b64encode(b"non sono un'immagine").decode()}
    r = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": dati, "applica": True})
    assert r.status_code == 200 and any("copertina" in a for a in r.json()["avvisi"])
    dati["corsi"][0]["copertina"] = {"jpeg_base64": "###non-base64###"}
    assert any("copertina" in a for a in client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": dati, "applica": True}).json()["avvisi"])


def test_una_copertina_grande_si_ridimensiona_come_al_caricamento(client, db, admin, auth, crea_corso):
    crea_corso("Excel")
    dati = client.get("/api/admin/configurazione/export", headers=auth(admin)).json()
    dati["corsi"][0]["copertina"] = {"jpeg_base64": base64.b64encode(jpeg(1920, 1080)).decode()}
    assert client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": dati, "applica": True}).status_code == 200
    db.expire_all()
    img = Image.open(io.BytesIO(cifratura.leggi_file(db.query(Corso).one().copertina_path)))
    assert img.size == (1280, 720)


def test_un_file_di_copertina_mancante_si_ripristina_con_l_import(client, db, admin, auth, crea_corso, formazione):
    c = crea_corso("Excel")
    assert client.post(f"/api/corsi/{c.id}/copertina", headers=auth(formazione), files={"file": ("c.png", png_storto(), "image/png")}).status_code == 200
    dati = client.get("/api/admin/configurazione/export", headers=auth(admin)).json()
    db.expire_all(); vecchio = db.get(Corso, c.id).copertina_path
    os.remove(vecchio)
    assert client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": dati, "applica": True}).status_code == 200
    db.expire_all(); nuovo = db.get(Corso, c.id).copertina_path
    assert nuovo and os.path.isfile(nuovo)


def test_l_import_non_supera_il_massimo_di_domande_e_rispetta_obbligatoria(client, db, admin, auth):
    from app.api.questionari import MAX_DOMANDE
    base = {"nome": "Pieno", "predefinito": False, "domande": [{"testo": f"D{i}", "tipo": "si_no", "opzioni": [], "obbligatoria": False} for i in range(MAX_DOMANDE)]}
    assert client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": {"formato": "elearning-configurazione", "schema": 3, "questionari": [base]}, "applica": True}).status_code == 200
    extra = {**base, "domande": [{"testo": "In piu'", "tipo": "si_no", "opzioni": [], "obbligatoria": False}]}
    r = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": {"formato": "elearning-configurazione", "schema": 3, "questionari": [extra]}, "applica": True}).json()
    assert any("In piu'" in a for a in r["avvisi"])
    from app.models.questionario import QuestionarioGradimento
    db.expire_all(); assert len(db.query(QuestionarioGradimento).filter_by(nome="Pieno").one().domande) == MAX_DOMANDE
    strano = {"nome": "Strano", "predefinito": False, "domande": [{"testo": "X", "tipo": "si_no", "opzioni": [], "obbligatoria": "forse"}]}
    r = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": {"formato": "elearning-configurazione", "schema": 3, "questionari": [strano]}, "applica": True}).json()
    assert any("Strano" in a for a in r["avvisi"])


def test_l_ordine_delle_domande_del_file_viene_applicato(client, db, admin, auth):
    def domande(*testi):
        return [{"testo": t, "tipo": "si_no", "opzioni": [], "obbligatoria": False} for t in testi]
    def invia(*testi):
        dati = {"formato": "elearning-configurazione", "schema": 3, "questionari": [{"nome": "Ordine", "predefinito": False, "domande": domande(*testi)}]}
        return client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": dati, "applica": True}).json()
    invia("A", "B", "C")
    r = invia("C", "A", "B")
    assert r["sezioni"]["questionari"]["aggiornati"][0]["campi"] == ["ordine"]
    db.expire_all()
    q = db.query(QuestionarioGradimento).filter_by(nome="Ordine").one()
    assert [d.testo for d in sorted(q.domande, key=lambda d: d.ordine)] == ["C", "A", "B"]
    assert invia("C", "A", "B")["totali"]["aggiornati"] == 0


def test_predefinito_non_booleano_e_un_avviso_e_questionario_non_testo_non_da_errore(client, db, admin, auth, crea_corso):
    crea_corso("Excel")
    dati = {"formato": "elearning-configurazione", "schema": 3,
            "questionari": [{"nome": "Falso", "predefinito": "false", "domande": []}],
            "corsi": [{"titolo": "Excel", "questionario": ["Aula"]}, {"titolo": "Word", "questionario": 5}]}
    r = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": dati, "applica": True})
    assert r.status_code == 200, r.text
    assert any("Falso" in a for a in r.json()["avvisi"]) and any("Excel" in a for a in r.json()["avvisi"])
    db.expire_all(); assert db.query(QuestionarioGradimento).filter_by(is_default=True).count() == 0


def test_voci_che_non_sono_oggetti_sono_avvisi_non_errori(client, db, admin, auth):
    dati = {"formato": "elearning-configurazione", "schema": 3, "questionari": [
        None, "testo", {"nome": "Domande storte", "domande": [None]},
        {"nome": "Buono", "domande": [{"testo": "Ok?", "tipo": "si_no"}]}]}
    r = client.post("/api/admin/configurazione/import", headers=auth(admin), json={"contenuto": dati, "applica": True})
    assert r.status_code == 200, r.text
    assert r.json()["sezioni"]["questionari"]["creati"] == ["Buono"] and len(r.json()["avvisi"]) == 3
