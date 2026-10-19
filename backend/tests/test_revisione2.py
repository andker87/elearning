"""Regressioni dalla seconda revisione del codice."""
import pytest

from app.config import Settings
from app.models.iscrizione import Iscrizione, StatoIscrizione as S
from app.models.edizione import StatoEdizione as SE
from app.models.notification import Notification
from app.models.user import User
from app.services import entra_sync as svc
from app.services import rate_limit
from app.services.email import _oggetto

from conftest import PASSWORD


# --- limite di login: contano solo i fallimenti -------------------------------------------------

def test_i_login_riusciti_non_consumano_il_limite_per_indirizzo(client, utente):
    for _ in range(40):  # es. l'inizio del turno: tanti accessi dallo stesso indirizzo (il proxy)
        assert client.post("/api/auth/login", json={"email": utente.email, "password": PASSWORD}).status_code == 200


def test_i_fallimenti_consumano_il_limite(client):
    codici = [client.post("/api/auth/login", json={"email": f"x{i}@t.it", "password": "x"}).status_code for i in range(32)]
    assert codici[30] == 429


def test_il_blocco_dell_account_non_manda_email_nel_login(client, db, admin, utente, monkeypatch):
    chiamate = []
    monkeypatch.setattr("app.services.email.invia_email", lambda *a, **k: chiamate.append(a) or True)
    monkeypatch.setattr("app.services.notifiche.invia_email", lambda *a, **k: chiamate.append(a) or True)
    for _ in range(5):
        client.post("/api/auth/login", json={"email": utente.email, "password": "x"})
    assert chiamate == []
    assert db.query(Notification).filter(Notification.user_id == admin.id, Notification.tipo == "account_bloccato").count() == 1


# --- rate limit: la memoria non cresce senza limite -------------------------------------------------

def test_le_chiavi_scadute_vengono_scartate(monkeypatch):
    monkeypatch.setattr(rate_limit, "_MAX_CHIAVI", 10)
    for n in range(50):
        rate_limit.registra(f"vecchia:{n}", finestra_secondi=0)
    import time; time.sleep(0.01)
    rate_limit.registra("nuova", finestra_secondi=0)
    assert len(rate_limit._eventi) < 20
    assert rate_limit.superato("inesistente", 1, 60) is False and "inesistente" not in rate_limit._eventi


# --- annullamento iscrizioni ---------------------------------------------------------------------------

def test_non_si_annulla_uno_storico_di_compliance(client, db, admin, auth, utente, crea_corso, crea_edizione, crea_iscrizione):
    ed = crea_edizione(crea_corso())
    fatta = crea_iscrizione(ed, utente, S.completato, giorni_fa=5)
    r = client.post(f"/api/edizioni/{ed.id}/iscrizioni/{fatta.id}/annulla", headers=auth(utente))
    assert r.status_code == 400
    db.refresh(fatta)
    assert fatta.stato == S.completato


def test_chi_era_in_lista_d_attesa_non_libera_un_posto(client, db, admin, auth, crea_utente, crea_corso, crea_edizione, crea_iscrizione):
    ed = crea_edizione(crea_corso(), stato=SE.pianificata, posti_max=1, lista_attesa_abilitata=True)
    titolare, b, c = crea_utente("t@test.it"), crea_utente("b@test.it"), crea_utente("c@test.it")
    crea_iscrizione(ed, titolare)
    ib = crea_iscrizione(ed, b, S.in_lista_attesa)
    ic = crea_iscrizione(ed, c, S.in_lista_attesa)
    assert client.post(f"/api/edizioni/{ed.id}/iscrizioni/{ib.id}/annulla", headers=auth(admin)).status_code == 200
    db.refresh(ic)
    assert ic.stato == S.in_lista_attesa            # nessun posto si e' liberato: niente promozioni
    assert db.query(Iscrizione).filter(Iscrizione.edizione_id == ed.id, Iscrizione.stato == S.iscritto).count() == 1


# --- configurazione: variabili vuote -----------------------------------------------------------------

def test_variabili_vuote_dal_compose_non_rompono_l_avvio(monkeypatch):
    for nome in ("SMTP_PORT", "SMTP_TLS", "SMTP_HOST", "SMTP_USER", "GRAPH_TENANT_ID"):
        monkeypatch.setenv(nome, "")
    s = Settings()
    assert s.SMTP_PORT is None and s.SMTP_TLS is True and not s.smtp_enabled


# --- disattivazione dal modulo utente ---------------------------------------------------------------------

def test_disattivare_dal_modulo_fa_l_offboarding_completo(client, db, admin, auth, utente, crea_corso, crea_edizione, crea_iscrizione):
    ed = crea_edizione(crea_corso(), stato=SE.pianificata)
    aperta = crea_iscrizione(ed, utente)
    utente.calendar_token_hash = "hash-finto"
    db.commit()
    r = client.put(f"/api/auth/users/{utente.id}", headers=auth(admin), json={"is_active": False})
    assert r.status_code == 200 and "avvisi_disattivazione" in r.json()
    db.refresh(aperta); db.refresh(utente)
    assert aperta.stato == S.annullato and utente.calendar_token_hash is None and utente.is_active is False
    assert client.put(f"/api/auth/users/{utente.id}", headers=auth(admin), json={"is_active": True}).json()["is_active"] is True


def test_non_si_disattiva_se_stessi_ne_l_ultimo_admin(client, admin, auth, crea_utente):
    assert client.put(f"/api/auth/users/{admin.id}", headers=auth(admin), json={"is_active": False}).status_code == 400
    altro = crea_utente("secondo.admin@test.it", ruolo="admin")
    assert client.put(f"/api/auth/users/{altro.id}", headers=auth(admin), json={"is_active": False}).status_code == 200
    # ora ne resta uno solo: chi lo disattivasse (un altro admin non c'e') non puo' farlo
    assert client.put(f"/api/auth/users/{admin.id}", headers=auth(admin), json={"is_active": False}).status_code == 400


# --- Entra: alias, UPN e mail diversi ------------------------------------------------------------------------

def test_entra_riconosce_la_persona_da_qualsiasi_suo_indirizzo(db, crea_utente, monkeypatch):
    registrato = crea_utente("mario.rossi@az.it")   # nella piattaforma con un indirizzo che Entra chiama alias
    membri = [{"email": "m.rossi@az.it", "indirizzi": ["m.rossi@az.it", "mario.rossi@az.it", "mrossi@az.onmicrosoft.com"],
               "nome": "Utente Test", "attivo": True, "assunto_il": None}]
    piano = svc.calcola_piano(db, membri)
    assert piano["disattiva"] == [] and piano["crea"] == []        # ne' esce, ne' si duplica
    assert piano["aggiorna"] == [] or piano["aggiorna"][0]["email"] == "mario.rossi@az.it"


# --- oggetto delle email -------------------------------------------------------------------------------------------

def test_l_oggetto_non_puo_spezzare_l_header():
    assert _oggetto("Avviso\r\nBcc: tutti@az.it") == "Avviso Bcc: tutti@az.it"
    assert len(_oggetto("x" * 500)) == 200
