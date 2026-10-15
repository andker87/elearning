"""Rilievi di CodeRabbit sulla correttezza (blocco 1.8.5): rinnovo, ingressi non validi, esportazioni, invii."""
import io
import json
from datetime import timedelta

from app.models.edizione import StatoEdizione as SE
from app.models.iscrizione import Iscrizione, StatoIscrizione as S
from app.services.rinnovo import esegui_rinnovi

from test_rinnovo import apri_sessione, completato, corso_rinnovabile


# --- rinnovo -----------------------------------------------------------------------------------

def test_il_rinnovo_rispetta_ripeti_entro(db, utente, crea_corso, crea_edizione, crea_iscrizione):
    from conftest import adesso
    corso = corso_rinnovabile(crea_corso)
    fatta = completato(crea_edizione, crea_iscrizione, corso, utente, giorni_fa=30)  # il corso scade fra 11 mesi...
    fatta.ripeti_entro = adesso() + timedelta(days=10)  # ...ma il test non superato chiede di ripeterlo entro 10 giorni
    db.commit()
    sessione = apri_sessione(crea_edizione, corso)
    assert "iscritti 1" in esegui_rinnovi(db)
    assert db.query(Iscrizione).filter(Iscrizione.edizione_id == sessione.id, Iscrizione.user_id == utente.id).count() == 1


def test_una_iscrizione_a_una_sessione_inutilizzabile_non_blocca_il_rinnovo(db, utente, crea_corso, crea_edizione, crea_iscrizione):
    from conftest import adesso
    corso = corso_rinnovabile(crea_corso)
    completato(crea_edizione, crea_iscrizione, corso, utente, giorni_fa=345)
    gia_iniziata = crea_edizione(corso, stato=SE.in_corso, data_inizio=adesso() - timedelta(days=3))
    crea_iscrizione(gia_iniziata, utente)  # aperta ma la sessione e' partita da giorni
    bozza = crea_edizione(corso, stato=SE.bozza)
    crea_iscrizione(bozza, utente)
    sessione = apri_sessione(crea_edizione, corso)
    assert "iscritti 1" in esegui_rinnovi(db)
    assert db.query(Iscrizione).filter(Iscrizione.edizione_id == sessione.id).count() == 1


# --- identificativi e dati in ingresso -------------------------------------------------------------

def test_un_filtro_etichette_non_uuid_e_un_errore_del_chiamante(client, formazione, auth):
    r = client.get("/api/dashboard/formazione/kpi", headers=auth(formazione), params={"etichette": "non-un-uuid"})
    assert r.status_code == 400


def test_identificativo_non_uuid_nel_percorso_non_e_un_500(client, formazione, auth):
    assert client.get("/api/certificato-templates/xyz/immagine", headers=auth(formazione)).status_code == 404
    assert client.get("/api/richieste-corso", headers=auth(formazione)).status_code == 200


def test_richiesta_corso_valida_gli_ingressi(client, formazione, auth, utente, crea_corso):
    h = auth(formazione)
    assert client.post("/api/richieste-corso", headers=h, json={"argomento": "   "}).status_code == 400
    assert client.post("/api/richieste-corso", headers=h, json={"corso_id": "xyz"}).status_code == 400
    assert client.post("/api/richieste-corso", headers=h, json={"argomento": "Primo soccorso", "persone_ids": ["xyz"]}).status_code == 400
    assert client.post("/api/richieste-corso", headers=h, json={"argomento": "Primo soccorso",
                       "persone_ids": ["00000000-0000-0000-0000-000000000000"]}).status_code == 404
    ok = client.post("/api/richieste-corso", headers=h, json={"argomento": " Primo soccorso ", "persone_ids": [str(utente.id), str(utente.id)]})
    assert ok.status_code == 200 and ok.json()["argomento"] == "Primo soccorso" and ok.json()["n_persone"] == 1


def test_una_richiesta_gia_valutata_non_si_rivaluta(client, formazione, auth):
    h = auth(formazione)
    rid = client.post("/api/richieste-corso", headers=h, json={"argomento": "Antincendio"}).json()["id"]
    assert client.put(f"/api/richieste-corso/{rid}/valuta", headers=h, json={"stato": "approvata"}).status_code == 200
    assert client.put(f"/api/richieste-corso/{rid}/valuta", headers=h, json={"stato": "rifiutata"}).status_code == 400


def test_template_attestato_rifiuta_campi_e_immagini_non_validi(client, formazione, auth):
    h = auth(formazione)
    tid = client.post("/api/certificato-templates", headers=h, json={"nome": "Base"}).json()["id"]
    chiave = client.get("/api/certificato-templates/campi-disponibili", headers=h).json()[0]["chiave"]
    for campo in ({"chiave": chiave, "x": "a"}, {"chiave": chiave, "x": 1, "y": 1, "font_size": 9999},
                  {"chiave": chiave, "x": 1, "y": 1, "colore": "rosso"}, {"chiave": chiave, "x": 1, "y": 1, "align": "diagonale"}):
        assert client.put(f"/api/certificato-templates/{tid}", headers=h, json={"campi": [campo]}).status_code == 400
    assert client.put(f"/api/certificato-templates/{tid}", headers=h, json={"campi": [{"chiave": chiave, "x": 10, "y": 20}]}).status_code == 200
    r = client.post(f"/api/certificato-templates/{tid}/immagine", headers=h, files={"file": ("a.png", b"non un'immagine", "image/png")})
    assert r.status_code == 400
    assert client.get(f"/api/certificato-templates/{tid}/anteprima.pdf", headers=h).status_code == 400  # nessuno sfondo e' stato salvato


def test_icona_troppo_grande_o_rotta_non_sostituisce_quella_buona(client, admin, auth):
    from PIL import Image
    h = auth(admin)
    buf = io.BytesIO(); Image.new("RGB", (256, 256), "red").save(buf, "PNG")
    assert client.post("/api/azienda/icona", headers=h, files={"file": ("i.png", buf.getvalue(), "image/png")}).status_code == 200
    troppo = b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024 + 10)
    assert client.post("/api/azienda/icona", headers=h, files={"file": ("i.png", troppo, "image/png")}).status_code == 400
    assert client.post("/api/azienda/icona", headers=h, files={"file": ("i.png", b"rotta", "image/png")}).status_code == 400
    assert client.get("/api/azienda/icona", params={"size": 64}).status_code == 200
    from app.models.azienda import Azienda
    import os
    from app.database import SessionLocal
    with SessionLocal() as s:
        assert os.path.exists(s.query(Azienda).first().icona_path)


# --- dashboard, esportazioni -------------------------------------------------------------------

def test_confronto_edizioni_con_date_mancanti(client, formazione, auth, crea_corso, crea_edizione):
    corso = crea_corso("Corso")
    crea_edizione(corso, stato=SE.pianificata, data_inizio=None)
    crea_edizione(corso, stato=SE.pianificata)
    r = client.get("/api/dashboard/kpi/confronto-edizioni", headers=auth(formazione), params={"corso_id": str(corso.id)})
    assert r.status_code == 200, r.text


def test_il_filtro_fine_dell_audit_con_orario_non_aggiunge_un_giorno(client, db, admin, auth):
    from app.models.audit import AuditLog
    from conftest import adesso
    ora = adesso()
    db.add(AuditLog(action="PROVA_ORARIO", created_at=ora - timedelta(hours=5)))
    db.add(AuditLog(action="PROVA_ORARIO", created_at=ora + timedelta(hours=3)))
    db.commit()
    fine = (ora - timedelta(hours=1)).replace(microsecond=0).isoformat()
    r = client.get("/api/admin/audit", headers=auth(admin), params={"action": "PROVA_ORARIO", "a": fine})
    assert r.json()["totale"] == 1


def test_l_esportazione_dell_audit_dichiara_il_taglio(client, db, admin, auth, monkeypatch):
    from app.api import admin_tecnico
    from app.models.audit import AuditLog
    for _ in range(3):
        db.add(AuditLog(action="TAGLIO"))
    db.commit()
    righe = {}
    originale = admin_tecnico.esporta

    def spia(formato, nome, titolo, colonne, dati, pagina="A4"):
        righe["dati"] = dati
        return originale(formato, nome, titolo, colonne, dati, pagina)
    monkeypatch.setattr(admin_tecnico, "esporta", spia)
    monkeypatch.setattr(admin_tecnico, "LIMITE_ESPORTAZIONE_CSV", 2)
    client.get("/api/admin/audit/export", headers=auth(admin), params={"action": "TAGLIO", "formato": "csv"})
    assert len(righe["dati"]) == 3 and "ATTENZIONE" in righe["dati"][-1]


def test_l_apice_anti_formula_non_finisce_nei_pdf():
    from app.services.export import _cella
    assert _cella("=1+1") == "'=1+1" and _cella("=1+1", neutra=False) == "=1+1"


def test_il_nome_dell_allegato_non_rompe_l_header():
    from app.services.email import _nome_allegato
    assert _nome_allegato('a"\r\nBcc: x@y.it/../b.ics') == "a_Bcc: x@y.it_.._b.ics"
    assert _nome_allegato("") == "allegato"


def test_il_ritorno_a_capo_nel_calendario_e_escapato():
    from app.services.calendario import _escape
    assert _escape("a\r\nb\rc\nd;e,f") == "a\\nb\\nc\\nd\;e\\,f"


def test_nessun_invito_calendario_per_una_sessione_in_bozza(db, monkeypatch, utente, crea_corso, crea_edizione):
    from app.config import settings
    from app.services import notifiche
    monkeypatch.setattr(type(settings), "smtp_enabled", property(lambda self: True))
    partiti = []
    monkeypatch.setattr(notifiche, "in_sottofondo", lambda *a: partiti.append(a))
    corso = crea_corso("Corso")
    assert notifiche.invia_invito_calendario(db, crea_edizione(corso, stato=SE.bozza), utente.id) is False
    assert notifiche.invia_invito_calendario(db, crea_edizione(corso, stato=SE.pianificata), utente.id) is True
    assert len(partiti) == 1


def test_sottoscrizione_push_ripetuta_non_crea_doppioni(client, utente, auth, db):
    from app.models.push_subscription import PushSubscription
    corpo = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "k", "auth": "a"}}
    assert client.post("/api/push/subscribe", headers=auth(utente), json=corpo).status_code == 200
    assert client.post("/api/push/subscribe", headers=auth(utente), json=corpo).status_code == 200
    assert db.query(PushSubscription).filter(PushSubscription.endpoint == corpo["endpoint"]).count() == 1


def test_la_salute_regge_senza_cartella_dei_video(client, admin, auth, monkeypatch):
    from app.api import admin_tecnico

    def manca(_):
        raise FileNotFoundError("assente")
    monkeypatch.setattr(admin_tecnico.shutil, "disk_usage", manca)
    r = client.get("/api/admin/salute", headers=auth(admin))
    assert r.status_code == 200 and r.json()["storage"]["disco_totale"] is None


def test_l_url_base_degli_inviti_ripulisce_spazi_e_barre(db, monkeypatch):
    from app.config import settings
    from app.services.inviti import url_base
    monkeypatch.setattr(settings, "SSO_PUBLIC_URL", "  https://formazione.example.it//  ")
    assert url_base(db) == "https://formazione.example.it"


def test_coordinate_impossibili_del_template_si_rifiutano(client, formazione, auth):
    h = auth(formazione)
    tid = client.post("/api/certificato-templates", headers=h, json={"nome": "Coord"}).json()["id"]
    chiave = client.get("/api/certificato-templates/campi-disponibili", headers=h).json()[0]["chiave"]
    enorme = json.loads("1" + "0" * 400)
    assert client.put(f"/api/certificato-templates/{tid}", headers=h, content=json.dumps({"campi": [{"chiave": chiave, "x": enorme, "y": 1}]}),
                      ).status_code in (400, 422)
    from app.services.certificati import _numero
    assert _numero(enorme, 7, 0, 10) == 7
