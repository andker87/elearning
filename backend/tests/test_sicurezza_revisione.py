"""Regressioni emerse dalla revisione del codice."""
from datetime import timedelta

from app.api.password_reset import RICHIESTE_PER_EMAIL
from app.config import settings
from app.models.azienda import Azienda
from app.models.user import User, UserRole

from conftest import PASSWORD, adesso


def attiva_smtp(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(settings, "SMTP_MITTENTE", "noreply@test.it")
    inviate = []
    monkeypatch.setattr("app.api.password_reset.invia_email", lambda a, o, c: inviate.append((a, o, c)) or True)
    return inviate


# --- il link di reset non si costruisce con dati della richiesta -----------------------------

def test_header_origin_falso_non_finisce_nel_link(client, db, utente, monkeypatch):
    inviate = attiva_smtp(monkeypatch)
    client.post("/api/auth/password-dimenticata", json={"email": utente.email}, headers={"Origin": "https://evil.example"})
    assert inviate == []  # nessun URL configurato: niente link, la richiesta va all'Admin tecnico


def test_link_solo_con_l_url_configurato(client, db, utente, monkeypatch):
    inviate = attiva_smtp(monkeypatch)
    db.add(Azienda(url_pubblico="https://formazione.acme.it"))
    db.commit()
    client.post("/api/auth/password-dimenticata", json={"email": utente.email}, headers={"Origin": "https://evil.example"})
    assert len(inviate) == 1 and "https://formazione.acme.it/reimposta-password?token=" in inviate[0][2] and "evil" not in inviate[0][2]


def test_limite_per_email_anche_cambiando_indirizzo(client, db, utente, monkeypatch):
    inviate = attiva_smtp(monkeypatch)
    db.add(Azienda(url_pubblico="https://f.acme.it"))
    db.commit()
    for n in range(RICHIESTE_PER_EMAIL + 4):
        client.post("/api/auth/password-dimenticata", json={"email": utente.email}, headers={"X-Forwarded-For": f"10.0.0.{n}"})
    assert len(inviate) == RICHIESTE_PER_EMAIL


# --- email senza distinzione di maiuscole -----------------------------------------------------

def test_login_e_reset_ignorano_le_maiuscole(client, crea_utente, monkeypatch):
    u = crea_utente("Mario.Rossi@Azienda.it")
    assert client.post("/api/auth/login", json={"email": "mario.rossi@azienda.it", "password": PASSWORD}).status_code == 200
    inviate = attiva_smtp(monkeypatch)
    from app.models.azienda import Azienda as A
    monkeypatch.setattr(settings, "SSO_PUBLIC_URL", "https://f.acme.it")
    client.post("/api/auth/password-dimenticata", json={"email": "MARIO.ROSSI@azienda.it"})
    assert len(inviate) == 1


def test_non_si_creano_due_utenti_che_differiscono_per_le_maiuscole(client, admin, auth, crea_utente):
    crea_utente("a@x.it")
    r = client.post("/api/auth/users", headers=auth(admin), json={"email": "A@x.it", "full_name": "Doppione", "password": PASSWORD})
    assert r.status_code == 400


# --- import cessati: scelta esplicita ---------------------------------------------------------

def test_il_nome_del_file_non_attiva_la_disattivazione(client, db, admin, auth, crea_utente):
    u = crea_utente("resta@az.it")
    r = client.post("/api/auth/users/import-csv", headers=auth(admin), files={"file": ("cessata_formazione_nuovi.csv", b"email,full_name\nresta@az.it,X\n", "text/csv")})
    assert r.status_code == 400 and "cessati" in r.json()["detail"]
    db.refresh(u)
    assert u.is_active


def test_i_cessati_non_includono_gli_admin_tecnici(client, db, admin, auth, crea_utente):
    altro_admin = crea_utente("altro.admin@az.it", UserRole.admin_tecnico)
    normale = crea_utente("esce@az.it")
    r = client.post("/api/auth/users/import-csv", headers=auth(admin), params={"modo": "cessati"},
                    files={"file": ("e.csv", b"email\naltro.admin@az.it\nesce@az.it\n", "text/csv")}).json()
    esiti = {x["email"]: x["esito"] for x in r["righe"]}
    assert esiti == {"altro.admin@az.it": "errore", "esce@az.it": "disattivato"}
    db.refresh(altro_admin); db.refresh(normale)
    assert altro_admin.is_active and not normale.is_active


# --- calendario e struttura dei responsabili ---------------------------------------------------

def test_feed_calendario_dopo_la_disattivazione(client, db, utente):
    utente.calendar_token = "tok-calendario"
    db.commit()
    assert client.get("/api/calendario/feed.ics", params={"token": "tok-calendario"}).status_code == 200
    utente.is_active = False
    db.commit()
    assert client.get("/api/calendario/feed.ics", params={"token": "tok-calendario"}).status_code == 404


def test_struttura_dei_responsabili_solo_per_se_stessi_o_formazione(client, auth, utente, formazione, crea_utente):
    altro = crea_utente("altro@test.it")
    for percorso in ("sottoposti", "uffici-guidati", "responsabili"):
        assert client.get(f"/api/auth/users/{utente.id}/{percorso}", headers=auth(utente)).status_code == 200
        assert client.get(f"/api/auth/users/{altro.id}/{percorso}", headers=auth(utente)).status_code == 403
        assert client.get(f"/api/auth/users/{altro.id}/{percorso}", headers=auth(formazione)).status_code == 200


# --- SSO e Admin tecnico ------------------------------------------------------------------------

def test_sso_non_collega_per_email_un_admin_tecnico():
    from app.api import sso
    import inspect
    assert "admin_non_collegabile" in inspect.getsource(sso._risolvi_utente)


# --- cambio password obbligatorio imposto dal server ----------------------------------------------

def test_con_password_assegnata_si_puo_solo_cambiarla(client, auth, crea_utente):
    u = crea_utente(password_da_cambiare=True)
    h = auth(u)
    assert client.get("/api/auth/me", headers=h).status_code == 200
    assert client.get("/api/privacy/informativa", headers=h).status_code == 403
    assert client.get("/api/edizioni", headers=h).status_code == 403
    r = client.put("/api/auth/me/password", headers=h, json={"current_password": PASSWORD, "new_password": "Scelta!DaMe12345"})
    assert r.status_code == 200
    nuovo = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/privacy/informativa", headers=nuovo).status_code == 200


def test_chi_usa_il_dominio_non_e_bloccato_dal_cambio_password(client, auth, crea_utente):
    u = crea_utente(password_da_cambiare=True, origine_credenziali="dominio")
    assert client.get("/api/privacy/informativa", headers=auth(u)).status_code == 200


# --- quarto giro di revisione ---------------------------------------------------------------------

def test_non_si_degrada_l_ultimo_admin_tecnico_ne_se_stessi(client, auth, admin, crea_utente):
    r = client.put(f"/api/auth/users/{admin.id}", json={"role": "user"}, headers=auth(admin))
    assert r.status_code == 400
    secondo = crea_utente("admin2@test.it", UserRole.admin_tecnico)
    # un altro admin si puo' degradare, se ne resta almeno uno attivo
    assert client.put(f"/api/auth/users/{secondo.id}", json={"role": "user"}, headers=auth(admin)).status_code == 200
    # ma non se stessi
    assert client.put(f"/api/auth/users/{admin.id}", json={"role": "user"}, headers=auth(admin)).status_code == 400


def test_autoiscrizione_solo_in_sessioni_aperte(client, auth, utente, crea_corso, crea_edizione):
    from app.models.edizione import StatoEdizione
    corso = crea_corso("Aperto", permetti_autoiscrizione=True)
    for stato in (StatoEdizione.chiusa, StatoEdizione.annullata, StatoEdizione.bozza):
        e = crea_edizione(corso, stato=stato)
        assert client.post(f"/api/autoiscrizioni/edizioni/{e.id}", headers=auth(utente)).status_code == 400
    aperta = crea_edizione(corso, stato=StatoEdizione.pianificata)
    assert client.post(f"/api/autoiscrizioni/edizioni/{aperta.id}", headers=auth(utente)).status_code == 200


def test_i_csv_neutralizzano_le_formule():
    from app.services.export import neutralizza, _a_csv
    for pericoloso in ("=1+1", "+cmd", "-2+3", "@SOMMA(A1)"):
        assert neutralizza(pericoloso).startswith("'")
    assert neutralizza("Mario Rossi") == "Mario Rossi"
    assert b"'=HYPERLINK" in _a_csv(["Nome"], [["=HYPERLINK(\"http://x\")"]])


def test_il_formatore_di_una_sessione_chiusa_non_gestisce_piu_il_test(db, crea_utente, crea_corso, crea_edizione):
    from app.api.test import _puo_gestire_test
    from app.models.edizione import EdizioneDocente, StatoEdizione
    doc = crea_utente("doc@test.it")
    corso = crea_corso("Con test")
    e = crea_edizione(corso, stato=StatoEdizione.chiusa)
    db.add(EdizioneDocente(edizione_id=e.id, user_id=doc.id)); db.commit()
    assert not _puo_gestire_test(db, doc, str(corso.id))
    e2 = crea_edizione(corso, stato=StatoEdizione.pianificata)
    db.add(EdizioneDocente(edizione_id=e2.id, user_id=doc.id)); db.commit()
    assert _puo_gestire_test(db, doc, str(corso.id))


def test_freno_entra_su_installazioni_piccole(db, crea_utente):
    from app.services.entra_sync import calcola_piano
    for n in range(4):
        crea_utente(f"p{n}@azienda.it")
    membri = [{"email": "altro@azienda.it", "indirizzi": ["altro@azienda.it"], "nome": "Altro", "attivo": True, "assunto_il": None}]
    piano = calcola_piano(db, membri)
    assert len(piano["disattiva"]) == 4 and piano["freno"]


def test_reset_password_invia_in_sottofondo_e_import_csv_dopo_il_commit():
    import inspect
    from app.api import password_reset, auth
    assert "in_sottofondo(invia_email" in inspect.getsource(password_reset.password_dimenticata)
    assert "dopo_il_commit(db, invia_invito" in inspect.getsource(auth)


# --- quinto giro: rilievi di CodeRabbit (blocco sicurezza e integrita') ---------------------------

def test_solo_logo_e_icona_sono_pubblici(client):
    import os
    os.makedirs("/app/uploads/azienda", exist_ok=True)
    for nome, pubblico in (("logo.png", True), ("informativa-privacy.pdf", False)):
        with open(f"/app/uploads/azienda/{nome}", "wb") as f:
            f.write(b"%PDF-1.4 x")
        assert (client.get(f"/uploads/azienda/{nome}").status_code == 200) is pubblico
    for percorso in ("azienda/logo./../informativa-privacy.pdf", "azienda/logo.png/../informativa-privacy.pdf", "azienda/logo.%2e%2e/informativa-privacy.pdf"):
        assert client.get(f"/uploads/{percorso}").status_code == 404
    for percorso in ("certificati/x.pdf", "attestati_esterni/x.pdf", "template_attestati/x.png"):
        assert client.get(f"/uploads/{percorso}").status_code == 404


def test_l_informativa_pdf_richiede_il_login(client, db, auth, utente):
    from app.models.azienda import Azienda
    with open("/app/uploads/azienda/informativa-privacy.pdf", "wb") as f:
        f.write(b"%PDF-1.4 x")
    db.add(Azienda(privacy_pdf_path="/app/uploads/azienda/informativa-privacy.pdf")); db.commit()
    assert client.get("/api/privacy/informativa.pdf").status_code in (401, 403)
    assert client.get("/api/privacy/informativa.pdf", headers=auth(utente)).status_code == 200


def test_il_nome_dell_allegato_esterno_non_esce_dalla_cartella(client, db, auth, formazione, crea_utente, crea_corso, crea_edizione, crea_iscrizione):
    from app.models.evidenza import Evidenza
    e = crea_edizione(crea_corso("C"))
    i = crea_iscrizione(e, crea_utente("p@test.it"))
    r = client.post(f"/api/edizioni/{e.id}/evidenze/{i.id}/upload", headers=auth(formazione),
                    files={"file": ("../../../tmp/x.pdf", b"%PDF-1.4", "application/pdf")})
    assert r.status_code == 200, r.text
    ev = db.query(Evidenza).filter(Evidenza.iscrizione_id == i.id).first()
    assert ev.file_allegato_path.startswith("/app/uploads/attestati_esterni/") and ".." not in ev.file_allegato_path


def test_sso_senza_email_usa_upn_solo_per_il_tenant_dichiarato():
    import pytest
    from app.services import sso
    tid = "11111111-2222-3333-4444-555555555555"
    ok = {"preferred_username": "Mario@Az.it", "tid": tid, "iss": f"https://login.microsoftonline.com/{tid}/v2.0"}
    assert sso.email_da_claims(ok) == "mario@az.it"
    for claims in ({"preferred_username": "mario@az.it"},
                   {"preferred_username": "mario@az.it", "tid": tid, "iss": "https://altro.idp.it/"}):
        with pytest.raises(sso.SsoErrore):
            sso.email_da_claims(claims)


def test_reset_manuale_solo_per_account_attivi_e_locali(client, db, auth, admin, crea_utente):
    from app.models.password_reset import RichiestaResetPassword
    u = crea_utente("sospeso@test.it", is_active=False)
    r = RichiestaResetPassword(user_id=u.id); db.add(r); db.commit()
    assert client.post(f"/api/auth/password-reset-richieste/{r.id}/genera", headers=auth(admin)).status_code == 400


def test_il_formatore_di_una_bozza_non_gestisce_il_test(db, crea_utente, crea_corso, crea_edizione):
    from app.api.test import _puo_gestire_test
    from app.models.edizione import EdizioneDocente, StatoEdizione
    doc = crea_utente("doc2@test.it")
    corso = crea_corso("Bozza")
    e = crea_edizione(corso, stato=StatoEdizione.bozza)
    db.add(EdizioneDocente(edizione_id=e.id, user_id=doc.id)); db.commit()
    assert not _puo_gestire_test(db, doc, str(corso.id))


def test_il_freno_entra_scatta_se_escono_tutti(db, crea_utente):
    from app.services.entra_sync import calcola_piano
    crea_utente("solo@azienda.it")
    membri = [{"email": "altro@azienda.it", "indirizzi": ["altro@azienda.it"], "nome": "Altro", "attivo": True, "assunto_il": None}]
    assert calcola_piano(db, membri)["freno"]


def test_il_database_impedisce_doppioni_anche_se_i_controlli_vengono_aggirati(db, crea_utente, crea_corso, crea_edizione, crea_iscrizione):
    import pytest
    from sqlalchemy.exc import IntegrityError
    from app.models.iscrizione import Iscrizione, StatoIscrizione
    from app.models.test import Gradimento
    e = crea_edizione(crea_corso("U"))
    u = crea_utente("u@test.it")
    i = crea_iscrizione(e, u)
    db.add(Iscrizione(edizione_id=e.id, user_id=u.id, stato=StatoIscrizione.iscritto))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    # una iscrizione annullata non conta: ci si puo' iscrivere di nuovo
    i.stato = StatoIscrizione.annullato; db.commit()
    db.add(Iscrizione(edizione_id=e.id, user_id=u.id, stato=StatoIscrizione.iscritto)); db.commit()
    iscr = db.query(Iscrizione).filter(Iscrizione.user_id == u.id, Iscrizione.stato == StatoIscrizione.iscritto).first()
    db.add(Gradimento(iscrizione_id=iscr.id, voto_corso=4)); db.commit()
    db.add(Gradimento(iscrizione_id=iscr.id, voto_corso=5))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_non_si_risponde_a_una_campagna_chiusa(client, db, auth, formazione, crea_ufficio, crea_utente):
    from app.models.fabbisogno import FabbisognoCampagna, FabbisognoCampagnaInvito, StatoCampagna
    resp = crea_utente("resp@test.it")
    uff = crea_ufficio("Ufficio X", responsabile=resp)
    c = FabbisognoCampagna(titolo="2026", creata_da_id=formazione.id, stato=StatoCampagna.chiusa)
    db.add(c); db.flush()
    inv = FabbisognoCampagnaInvito(campagna_id=c.id, ufficio_id=uff.id); db.add(inv); db.commit()
    r = client.post(f"/api/fabbisogno/inviti/{inv.id}/delega", headers=auth(resp))
    assert r.status_code == 400 and "chiusa" in r.json()["detail"]


def test_i_posti_liberati_contano_solo_chi_occupava_un_posto(db, crea_utente, crea_corso, crea_edizione, crea_iscrizione):
    from app.models.edizione import StatoEdizione
    from app.models.iscrizione import StatoIscrizione
    from app.services.offboarding import disattiva_utente
    e = crea_edizione(crea_corso("L"), stato=StatoEdizione.pianificata, posti_max=1, lista_attesa_abilitata=True)
    primo, secondo = crea_utente("a@test.it"), crea_utente("b@test.it")
    crea_iscrizione(e, primo)
    crea_iscrizione(e, secondo, stato=StatoIscrizione.in_lista_attesa)
    esito = disattiva_utente(db, secondo)
    assert esito["posti_liberati"] == 0
