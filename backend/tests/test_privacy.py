"""Informativa privacy ed export dei dati personali."""
import json
import os

import pytest

from app.api import privacy

PDF = b"%PDF-1.4\n%%EOF\n"


@pytest.fixture(autouse=True)
def pdf_isolato(tmp_path, monkeypatch):
    percorso = tmp_path / "informativa-privacy.pdf"
    monkeypatch.setattr(privacy, "INFORMATIVA_DIR", str(tmp_path))
    monkeypatch.setattr(privacy, "INFORMATIVA_PDF", str(percorso))
    return percorso


def test_informativa_vuota_all_inizio(client, utente, auth):
    r = client.get("/api/privacy/informativa", headers=auth(utente)).json()
    assert r["presente"] is False and r["testo"] is None and r["pdf_url"] is None


def test_admin_salva_il_testo_e_tutti_lo_leggono(client, admin, utente, auth):
    r = client.put("/api/privacy/informativa", headers=auth(admin), json={"testo": "  Titolare: Acme  "})
    assert r.status_code == 200
    letto = client.get("/api/privacy/informativa", headers=auth(utente)).json()
    assert letto["presente"] and letto["testo"] == "Titolare: Acme" and letto["aggiornata_at"]
    client.put("/api/privacy/informativa", headers=auth(admin), json={"testo": ""})
    assert client.get("/api/privacy/informativa", headers=auth(utente)).json()["presente"] is False


def test_solo_admin_modifica(client, formazione, utente, auth):
    for persona in (formazione, utente):
        assert client.put("/api/privacy/informativa", headers=auth(persona), json={"testo": "x"}).status_code == 403
        assert client.post("/api/privacy/informativa/pdf", headers=auth(persona), files={"file": ("a.pdf", PDF, "application/pdf")}).status_code == 403
        assert client.delete("/api/privacy/informativa/pdf", headers=auth(persona)).status_code == 403


def test_pdf_deve_essere_un_pdf_vero(client, admin, auth, pdf_isolato):
    finto = client.post("/api/privacy/informativa/pdf", headers=auth(admin), files={"file": ("a.pdf", b"non e' un pdf", "application/pdf")})
    assert finto.status_code == 400 and not pdf_isolato.exists()
    vero = client.post("/api/privacy/informativa/pdf", headers=auth(admin), files={"file": ("a.pdf", PDF, "application/pdf")})
    assert vero.status_code == 200 and vero.json()["pdf_url"] and pdf_isolato.exists()
    rimosso = client.delete("/api/privacy/informativa/pdf", headers=auth(admin))
    assert rimosso.json()["pdf_url"] is None and not pdf_isolato.exists()


def test_pdf_troppo_grande(client, admin, auth, monkeypatch):
    monkeypatch.setattr(privacy, "INFORMATIVA_MAX_BYTES", 10)
    r = client.post("/api/privacy/informativa/pdf", headers=auth(admin), files={"file": ("a.pdf", PDF + b"x" * 50, "application/pdf")})
    assert r.status_code == 400


def test_modifiche_all_informativa_finiscono_nell_audit(client, admin, auth):
    client.put("/api/privacy/informativa", headers=auth(admin), json={"testo": "x"})
    voci = client.get("/api/admin/audit", headers=auth(admin), params={"q": "Informativa"}).json()["items"]
    assert any(v["entity_name"] == "Informativa privacy" for v in voci)


def test_export_dati_personali_senza_segreti(client, utente, crea_utente, crea_corso, crea_edizione, crea_iscrizione, auth):
    crea_iscrizione(crea_edizione(crea_corso("Mio corso")), utente)
    altro = crea_utente("altro@test.it", full_name="Altra Persona")
    r = client.get("/api/privacy/export", headers=auth(utente))
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    dati = json.loads(r.text)
    assert dati["profilo"]["email"] == utente.email and len(dati["iscrizioni"]) == 1
    testo = r.text
    for segreto in ("hashed_password", "calendar_token_hash", "sso_subject", "token_version"):
        assert segreto not in testo, segreto
    assert "hashed_password" not in dati["profilo"] and "calendar_token_hash" not in dati["profilo"]
    assert altro.email not in testo  # nessun dato di altre persone
