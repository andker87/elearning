"""Regressioni dalla terza revisione del codice."""
import io

from app.models.edizione import EdizioneDocente, RuoloDocente, StatoEdizione as SE
from app.models.group import Group
from app.models.iscrizione import Iscrizione, StatoIscrizione as S
from app.models.test import Domanda, OpzioneRisposta, Test
from app.services.gerarchia import persone_ufficio_e_sottouffici, responsabili_di, sottoposti_di


def test_niente_cicli_nella_gerarchia(client, db, admin, auth, crea_ufficio, crea_utente):
    a = crea_ufficio("A")
    b = crea_ufficio("B")
    b.parent_id = a.id
    db.commit()
    assert client.put(f"/api/groups/{a.id}", headers=auth(admin), json={"parent_id": str(b.id)}).status_code == 400   # A sotto B sotto A
    assert client.put(f"/api/groups/{a.id}", headers=auth(admin), json={"parent_id": str(a.id)}).status_code == 400   # A sotto se stesso
    c = crea_ufficio("C")
    assert client.put(f"/api/groups/{c.id}", headers=auth(admin), json={"parent_id": str(b.id)}).status_code == 200


def test_la_gerarchia_non_gira_in_tondo_anche_con_dati_incoerenti(db, crea_utente, crea_ufficio):
    capo, persona = crea_utente("capo@test.it"), crea_utente("persona@test.it")
    a = crea_ufficio("A", membri=[persona], responsabile=capo)
    b = crea_ufficio("B")
    a.parent_id, b.parent_id = b.id, a.id   # ciclo scritto direttamente nel database
    db.commit()
    assert [p.email for p in persone_ufficio_e_sottouffici(db, str(a.id))] == ["persona@test.it"]
    assert {u.email for u in sottoposti_di(db, str(capo.id))} == {"persona@test.it"}
    responsabili_di(db, str(persona.id))  # non deve bloccarsi


def test_il_formatore_che_modifica_un_test_non_perde_le_risposte_giuste(client, db, auth, crea_utente, crea_corso, crea_edizione):
    corso = crea_corso("Con test")
    docente = crea_utente("docente@test.it")
    ed = crea_edizione(corso, stato=SE.pianificata)
    db.add(EdizioneDocente(edizione_id=ed.id, user_id=docente.id, ruolo=RuoloDocente.titolare))
    t = Test(corso_id=corso.id, titolo="Finale")
    db.add(t); db.flush()
    d = Domanda(test_id=t.id, testo="2+2?", ordine=0)
    db.add(d); db.flush()
    db.add_all([OpzioneRisposta(domanda_id=d.id, testo="4", corretta=True), OpzioneRisposta(domanda_id=d.id, testo="5", corretta=False)])
    db.commit()
    letto = client.get(f"/api/test/{t.id}", headers=auth(docente)).json()
    assert any(o.get("corretta") for o in letto["domande"][0]["opzioni"])        # il formatore le vede
    client.put(f"/api/test/{t.id}", headers=auth(docente), json=letto)          # e salvando restano
    rilette = client.get(f"/api/test/{t.id}", headers=auth(docente)).json()
    assert [o["corretta"] for o in rilette["domande"][0]["opzioni"]] == [True, False]
    discente = crea_utente("discente@test.it")
    assert "corretta" not in client.get(f"/api/test/{t.id}", headers=auth(discente)).json()["domande"][0]["opzioni"][0]


def test_pianificare_due_volte_o_una_sessione_chiusa(client, db, formazione, auth, crea_corso, crea_edizione):
    bozza = crea_edizione(crea_corso(), stato=SE.bozza)
    assert client.post(f"/api/edizioni/{bozza.id}/pianifica", headers=auth(formazione)).status_code == 200
    assert client.post(f"/api/edizioni/{bozza.id}/pianifica", headers=auth(formazione)).status_code == 200   # nessun effetto
    chiusa = crea_edizione(crea_corso(), stato=SE.chiusa)
    assert client.post(f"/api/edizioni/{chiusa.id}/pianifica", headers=auth(formazione)).status_code == 400
    db.refresh(chiusa)
    assert chiusa.stato == SE.chiusa


def test_logo_non_valido_rifiutato_e_icona_sempre_disponibile(client, db, admin, auth):
    r = client.post("/api/azienda/logo", headers=auth(admin), files={"file": ("logo.png", b"non sono un'immagine", "image/png")})
    assert r.status_code == 400
    from app.models.azienda import Azienda
    import tempfile, os
    rotto = tempfile.NamedTemporaryFile(suffix=".png", delete=False); rotto.write(b"rotto"); rotto.close()
    db.add(Azienda(logo_path=rotto.name)); db.commit()
    risposta = client.get("/api/azienda/icona", params={"size": 192})
    os.unlink(rotto.name)
    assert risposta.status_code == 200 and risposta.headers["content-type"] == "image/png"
    assert risposta.content[:8] == b"\x89PNG\r\n\x1a\n"  # ripiega sul marchio: un PNG vero, non un file vuoto


def test_iscrivere_piu_persone_dei_posti(client, db, formazione, auth, crea_utente, crea_corso, crea_edizione):
    ed = crea_edizione(crea_corso(), stato=SE.pianificata, posti_max=2)
    persone = [crea_utente(f"p{n}@test.it") for n in range(4)]
    r = client.post(f"/api/edizioni/{ed.id}/iscrizioni", headers=auth(formazione), json=[str(p.id) for p in persone])
    assert r.status_code == 200 and len(r.json()["iscritti"]) == 2 and len(r.json()["non_iscritti"]) == 2
    assert db.query(Iscrizione).filter(Iscrizione.edizione_id == ed.id, Iscrizione.stato == S.iscritto).count() == 2  # mai oltre la capienza


def test_non_si_iscrive_in_una_sessione_chiusa_o_in_bozza(client, db, formazione, auth, crea_utente, crea_corso, crea_edizione, crea_ufficio):
    capo, persona = crea_utente("capo@test.it"), crea_utente("persona@test.it")
    crea_ufficio("Uff", membri=[persona], responsabile=capo)
    chiusa = crea_edizione(crea_corso(), stato=SE.chiusa)
    bozza = crea_edizione(crea_corso(), stato=SE.bozza)
    assert client.post(f"/api/edizioni/{chiusa.id}/iscrizioni", headers=auth(formazione), json=[str(persona.id)]).status_code == 400
    assert client.post(f"/api/edizioni/{bozza.id}/iscrizioni", headers=auth(capo), json=[str(persona.id)]).status_code == 400
    assert client.post(f"/api/edizioni/{bozza.id}/iscrizioni", headers=auth(formazione), json=[str(persona.id)]).status_code == 200


def test_aumentare_i_posti_fa_salire_chi_aspetta(client, db, formazione, auth, crea_utente, crea_corso, crea_edizione, crea_iscrizione):
    ed = crea_edizione(crea_corso(), stato=SE.pianificata, posti_max=1, lista_attesa_abilitata=True)
    crea_iscrizione(ed, crea_utente("dentro@test.it"))
    attesa = [crea_iscrizione(ed, crea_utente(f"a{n}@test.it"), S.in_lista_attesa) for n in range(3)]
    corpo = {"corso_id": str(ed.corso_id), "modalita": "esterna", "posti_max": 3, "lista_attesa_abilitata": True}
    assert client.put(f"/api/edizioni/{ed.id}", headers=auth(formazione), json=corpo).status_code == 200
    stati = [db.query(Iscrizione).filter(Iscrizione.id == i.id).one().stato for i in attesa]
    assert stati == [S.iscritto, S.iscritto, S.in_lista_attesa]  # due posti in piu': salgono i primi due arrivati


def test_chi_sale_dalla_lista_dopo_una_disattivazione_riceve_l_invito(client, db, admin, auth, crea_utente, crea_corso, crea_edizione, crea_iscrizione, monkeypatch):
    inviti = []
    monkeypatch.setattr("app.services.notifiche.invia_invito_calendario", lambda db, ed, uid: inviti.append(uid) or True)
    ed = crea_edizione(crea_corso(), stato=SE.pianificata, posti_max=1, lista_attesa_abilitata=True)
    esce, aspetta = crea_utente("esce@test.it"), crea_utente("aspetta@test.it")
    crea_iscrizione(ed, esce)
    crea_iscrizione(ed, aspetta, S.in_lista_attesa)
    client.put(f"/api/auth/users/{esce.id}", headers=auth(admin), json={"is_active": False})
    assert inviti == [aspetta.id]


def test_le_email_delle_notifiche_partono_solo_dopo_il_commit(db, utente, monkeypatch):
    from app.services import email as email_svc
    from app.services.notifiche import _crea_se_assente
    partite = []
    monkeypatch.setattr(email_svc, "in_sottofondo", lambda f, *a: partite.append(a))
    _crea_se_assente(db, utente.id, "prova", "testo", dedup_key="prova:1")
    db.rollback()
    assert partite == []          # transazione annullata: nessuna email
    _crea_se_assente(db, utente.id, "prova", "testo", dedup_key="prova:2")
    db.commit()
    assert len(partite) == 1 and partite[0][0] == utente.email
