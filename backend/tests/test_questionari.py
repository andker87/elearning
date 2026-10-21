"""2.8.0: questionari di gradimento personalizzabili dalla Formazione."""
import pytest

from app.models.corso import Corso
from app.models.edizione import EdizioneDocente, RuoloDocente, StatoEdizione as SE
from app.models.iscrizione import StatoIscrizione as S
from app.models.questionario import QuestionarioGradimento
from app.models.test import Gradimento, RispostaGradimento


DOMANDE = [
    {"testo": "Il tono era adatto?", "tipo": "stelle", "obbligatoria": True},
    {"testo": "Lo consiglieresti?", "tipo": "si_no"},
    {"testo": "Quale parte ti è servita di più?", "tipo": "scelta", "opzioni": ["Teoria", "Esempi", "Esercizi"]},
    {"testo": "Cosa cambieresti?", "tipo": "testo"},
]


def crea_q(client, auth, formazione, nome="Soft skills", predefinito=True, domande=None):
    return client.post("/api/questionari", headers=auth(formazione), json={"nome": nome, "is_default": predefinito, "domande": DOMANDE if domande is None else domande})


@pytest.fixture
def iscrizione(db, utente, crea_corso, crea_edizione, crea_iscrizione, crea_utente):
    c = crea_corso("Comunicazione efficace")
    e = crea_edizione(c, stato=SE.chiusa)
    docente = crea_utente("doc@t.it", nome="Dora", cognome="Docente")
    db.add(EdizioneDocente(edizione_id=e.id, user_id=docente.id, ruolo=RuoloDocente.titolare)); db.commit()
    return crea_iscrizione(e, utente, stato=S.completato), c, docente


def test_solo_la_formazione_gestisce_i_questionari(client, auth, utente, formazione):
    assert client.get("/api/questionari", headers=auth(utente)).status_code == 403
    assert client.post("/api/questionari", headers=auth(utente), json={"nome": "X", "domande": []}).status_code == 403
    r = crea_q(client, auth, formazione)
    assert r.status_code == 200 and r.json()["is_default"] is True and [d["tipo"] for d in r.json()["domande"]] == ["stelle", "si_no", "scelta", "testo"]


def test_le_domande_si_controllano(client, auth, formazione):
    cattive = [
        [{"testo": "", "tipo": "testo"}],
        [{"testo": "x", "tipo": "inventato"}],
        [{"testo": "Scegli", "tipo": "scelta", "opzioni": ["Una sola"]}],
        [{"testo": "Scegli", "tipo": "scelta", "opzioni": ["A", "A"]}],
        [{"testo": "d", "tipo": "testo"}] * 21,
    ]
    for domande in cattive:
        assert client.post("/api/questionari", headers=auth(formazione), json={"nome": "Q", "domande": domande}).status_code in (400, 422), domande
    assert crea_q(client, auth, formazione, nome="Ok").status_code == 200
    assert crea_q(client, auth, formazione, nome="Ok").status_code == 400                      # nome gia' usato


def test_uno_solo_e_il_predefinito_e_si_puo_modificare_ed_eliminare(client, auth, formazione, db, crea_corso):
    a = crea_q(client, auth, formazione, "A").json()
    b = crea_q(client, auth, formazione, "B", predefinito=True).json()
    db.expire_all()
    assert [q.is_default for q in db.query(QuestionarioGradimento).order_by(QuestionarioGradimento.nome)] == [False, True]
    r = client.put(f"/api/questionari/{a['id']}", headers=auth(formazione), json={"nome": "A2", "is_default": False, "domande": DOMANDE[:1]})
    assert r.status_code == 200 and r.json()["nome"] == "A2" and len(r.json()["domande"]) == 1
    c = crea_corso("Corso"); c.questionario_gradimento_id = a["id"]; db.commit()
    r = client.delete(f"/api/questionari/{a['id']}", headers=auth(formazione))
    assert r.status_code == 409 and "1 corso" in r.json()["detail"]                             # scelto da un corso: non si toglie
    assert client.delete(f"/api/questionari/{b['id']}", headers=auth(formazione)).status_code == 200


def test_il_corso_sceglie_il_questionario(client, auth, formazione, db):
    q = crea_q(client, auth, formazione, "Dedicato", predefinito=False).json()
    corso = client.post("/api/corsi", headers=auth(formazione), json={"titolo": "Corso", "questionario_gradimento_id": q["id"]}).json()
    assert corso["questionario_gradimento_id"] == q["id"]
    # una modifica che non lo nomina non lo cancella; "" lo riporta al predefinito
    r = client.put(f"/api/corsi/{corso['id']}", headers=auth(formazione), json={"titolo": "Corso", "durata_minuti": 30})
    assert r.json()["questionario_gradimento_id"] == q["id"]
    r = client.put(f"/api/corsi/{corso['id']}", headers=auth(formazione), json={"titolo": "Corso", "questionario_gradimento_id": ""})
    assert r.json()["questionario_gradimento_id"] is None
    assert client.post("/api/corsi", headers=auth(formazione), json={"titolo": "Altro", "questionario_gradimento_id": "non-un-id"}).status_code == 400
    assert client.post("/api/corsi", headers=auth(formazione), json={"titolo": "Altro", "questionario_gradimento_id": "00000000-0000-0000-0000-000000000000"}).status_code == 400


def test_il_modulo_mostra_le_domande_del_corso_o_il_predefinito(client, auth, utente, formazione, db, iscrizione):
    i, corso, docente = iscrizione
    modulo = client.get(f"/api/iscrizioni/{i.id}/gradimento/modulo", headers=auth(utente)).json()
    assert modulo["domande"] == [] and modulo["gia_inviato"] is False and modulo["docenti"][0]["nome"] == "Dora Docente"       # senza questionari: solo le domande fisse
    crea_q(client, auth, formazione, "Predefinito")
    assert len(client.get(f"/api/iscrizioni/{i.id}/gradimento/modulo", headers=auth(utente)).json()["domande"]) == 4
    dedicato = crea_q(client, auth, formazione, "Dedicato", predefinito=False, domande=[{"testo": "Solo questa", "tipo": "testo"}]).json()
    corso.questionario_gradimento_id = dedicato["id"]; db.commit()
    assert [d["testo"] for d in client.get(f"/api/iscrizioni/{i.id}/gradimento/modulo", headers=auth(utente)).json()["domande"]] == ["Solo questa"]
    assert client.get(f"/api/iscrizioni/{i.id}/gradimento/modulo", headers=auth(formazione)).status_code == 403              # il modulo e' di chi ha seguito il corso


def test_invio_con_le_domande_aggiuntive(client, auth, utente, formazione, db, iscrizione):
    i, corso, docente = iscrizione
    crea_q(client, auth, formazione, "Predefinito")
    d = {x["testo"]: x for x in client.get(f"/api/iscrizioni/{i.id}/gradimento/modulo", headers=auth(utente)).json()["domande"]}
    url = f"/api/iscrizioni/{i.id}/gradimento"
    base = {"voto_corso": 4, "commento_corso": "Bello", "voti_docenti": {str(docente.id): 5}}
    # obbligatoria mancante, tipi sbagliati, domanda estranea
    assert client.post(url, headers=auth(utente), json={**base, "risposte": {}}).status_code == 400
    assert client.post(url, headers=auth(utente), json={**base, "risposte": {d["Il tono era adatto?"]["id"]: 9}}).status_code == 400
    assert client.post(url, headers=auth(utente), json={**base, "risposte": {d["Il tono era adatto?"]["id"]: 4, d["Lo consiglieresti?"]["id"]: "forse"}}).status_code == 400
    assert client.post(url, headers=auth(utente), json={**base, "risposte": {d["Il tono era adatto?"]["id"]: 4, d["Quale parte ti è servita di più?"]["id"]: "Altro"}}).status_code == 400
    assert client.post(url, headers=auth(utente), json={**base, "risposte": {d["Il tono era adatto?"]["id"]: 4, "00000000-0000-0000-0000-000000000000": 1}}).status_code == 400
    assert db.query(Gradimento).count() == 0                                                    # niente a meta'
    ok = client.post(url, headers=auth(utente), json={**base, "risposte": {
        d["Il tono era adatto?"]["id"]: 4, d["Lo consiglieresti?"]["id"]: "si",
        d["Quale parte ti è servita di più?"]["id"]: "Esempi", d["Cosa cambieresti?"]["id"]: "  Più esempi  "}})
    assert ok.status_code == 200, ok.text
    assert db.query(RispostaGradimento).count() == 4
    assert client.post(url, headers=auth(utente), json={**base, "risposte": {d["Il tono era adatto?"]["id"]: 4}}).status_code == 400    # una sola volta
    assert client.get(f"/api/iscrizioni/{i.id}/gradimento/modulo", headers=auth(utente)).json()["gia_inviato"] is True


def test_report_con_le_domande_aggiuntive_anche_se_poi_cambiano(client, auth, utente, formazione, db, iscrizione):
    i, corso, docente = iscrizione
    q = crea_q(client, auth, formazione, "Predefinito").json()
    d = {x["testo"]: x["id"] for x in q["domande"]}
    client.post(f"/api/iscrizioni/{i.id}/gradimento", headers=auth(utente), json={"voto_corso": 5, "risposte": {
        d["Il tono era adatto?"]: 3, d["Lo consiglieresti?"]: "si", d["Quale parte ti è servita di più?"]: "Teoria", d["Cosa cambieresti?"]: "Niente"}})
    # la Formazione riscrive il questionario: il report passato resta leggibile
    client.put(f"/api/questionari/{q['id']}", headers=auth(formazione), json={"nome": "Predefinito", "is_default": True, "domande": [{"testo": "Nuova", "tipo": "testo"}]})
    rep = client.get(f"/api/edizioni/{i.edizione_id}/gradimenti", headers=auth(formazione)).json()
    per = {x["testo"]: x for x in rep["domande"]}
    assert per["Il tono era adatto?"]["media"] == 3 and per["Lo consiglieresti?"]["conteggi"] == {"si": 1}
    assert per["Quale parte ti è servita di più?"]["conteggi"] == {"Teoria": 1} and per["Cosa cambieresti?"]["testi"] == ["Niente"]
    csv_ = client.get(f"/api/edizioni/{i.edizione_id}/report/gradimenti.csv", headers=auth(formazione)).text
    riga0 = csv_.splitlines()[0]
    assert "Il tono era adatto?" in riga0 and "Cosa cambieresti?" in riga0 and "Dora" in riga0
    assert client.get(f"/api/edizioni/{i.edizione_id}/gradimenti", headers=auth(utente)).status_code == 403


def test_il_nome_gia_usato_in_parallelo_da_un_400_e_non_un_500(client, auth, formazione, db, monkeypatch):
    """Il controllo del nome passa (due richieste insieme), ma il database ferma il secondo salvataggio."""
    from app.api import questionari as modulo
    crea_q(client, auth, formazione, "Doppio", predefinito=False)
    monkeypatch.setattr(modulo, "_controlla_nome", lambda *a, **k: None)             # simula la corsa: il controllo non vede il doppione
    r = crea_q(client, auth, formazione, "Doppio", predefinito=False)
    assert r.status_code == 400 and "nome" in r.json()["detail"]
    altro = crea_q(client, auth, formazione, "Altro", predefinito=False).json()
    r = client.put(f"/api/questionari/{altro['id']}", headers=auth(formazione), json={"nome": "Doppio", "is_default": False, "domande": []})
    assert r.status_code == 400 and "nome" in r.json()["detail"]
    db.expire_all(); assert db.query(QuestionarioGradimento).count() == 2


def test_due_domande_con_lo_stesso_testo_non_sono_ammesse(client, auth, formazione):
    doppie = [{"testo": "Il tono?", "tipo": "stelle"}, {"testo": "  il   TONO? ", "tipo": "testo"}]
    r = crea_q(client, auth, formazione, "Doppie", predefinito=False, domande=doppie)
    assert r.status_code == 400 and "stesso testo" in r.json()["detail"]
    ok = crea_q(client, auth, formazione, "Singole", predefinito=False, domande=[doppie[0], {"testo": "Altro?", "tipo": "testo"}])
    assert ok.status_code == 200
    r = client.put(f"/api/questionari/{ok.json()['id']}", headers=auth(formazione), json={"nome": "Singole", "is_default": False, "domande": doppie})
    assert r.status_code == 400


def test_un_doppio_invio_del_gradimento_in_parallelo_da_400(client, auth, utente, db, iscrizione, monkeypatch):
    """Il controllo «gia' inviato» non vede il primo invio (corsa), ma il vincolo del database ferma il secondo."""
    i, corso, docente = iscrizione
    url = f"/api/iscrizioni/{i.id}/gradimento"
    assert client.post(url, headers=auth(utente), json={"voto_corso": 4, "voti_docenti": {str(docente.id): 5}}).status_code == 200

    from app.api import gradimenti as modulo
    saltati = []
    class SenzaDoppione:                       # il controllo preventivo non trova il gradimento gia' presente
        def __init__(self, q): self.q = q
        def filter(self, *a, **k): return SenzaDoppione(self.q.filter(*a, **k))
        def first(self): saltati.append(True); return None
    from sqlalchemy.orm import Session
    originale = Session.query
    monkeypatch.setattr(Session, "query", lambda self, *a, **k: SenzaDoppione(originale(self, *a, **k)) if a and a[0] is modulo.Gradimento else originale(self, *a, **k))
    r = client.post(url, headers=auth(utente), json={"voto_corso": 3, "voti_docenti": {str(docente.id): 4}})
    monkeypatch.undo()
    assert saltati, "il controllo preventivo doveva essere aggirato per provare la corsa"
    assert r.status_code == 400 and "già inviato" in r.json()["detail"]
    assert db.query(modulo.Gradimento).count() == 1
