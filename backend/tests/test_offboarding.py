"""Offboarding e sincronizzazione utenti da Entra (Graph simulato)."""
import pytest

from app.services.impronte import impronta
from app.config import settings
from app.models.audit import AuditLog
from app.models.edizione import EdizioneDocente, RuoloDocente, StatoEdizione
from app.models.group import Group
from app.models.iscrizione import Iscrizione, StatoIscrizione as S
from app.models.job_run import JobRun
from app.models.notification import Notification
from app.models.push_subscription import PushSubscription
from app.models.user import User, UserRole
from app.services import entra_sync as svc
from app.services.job_tracking import esegui_tracciato
from app.services.offboarding import disattiva_utente


def membro(email, nome="Nome", attivo=True, assunto=None):
    return {"email": email, "nome": nome, "attivo": attivo, "assunto_il": assunto}


@pytest.fixture
def entra(monkeypatch):
    """Graph finto: il test imposta entra.membri; la configurazione risulta attiva."""
    monkeypatch.setattr(settings, "GRAPH_TENANT_ID", "t")
    monkeypatch.setattr(settings, "GRAPH_CLIENT_ID", "c")
    monkeypatch.setattr(settings, "GRAPH_CLIENT_SECRET", "s")
    monkeypatch.setattr(settings, "ENTRA_SYNC_GRUPPO_ID", "gruppo")

    class Finto:
        membri = []
        errore = None
    def leggi():
        if Finto.errore:
            raise svc.EntraErrore(Finto.errore)
        return list(Finto.membri)
    monkeypatch.setattr(svc, "leggi_membri", leggi)
    return Finto


# --- disattivazione di una persona ------------------------------------------------------

def test_disattivazione_libera_i_posti_e_promuove_la_lista_d_attesa(db, crea_utente, crea_corso, crea_edizione, crea_iscrizione):
    ed = crea_edizione(crea_corso(), stato=StatoEdizione.pianificata, posti_max=1, lista_attesa_abilitata=True)
    esce, attende = crea_utente("esce@test.it"), crea_utente("attende@test.it")
    crea_iscrizione(ed, esce)
    crea_iscrizione(ed, attende, S.in_lista_attesa)
    db.add(PushSubscription(user_id=esce.id, endpoint="https://p", p256dh="a", auth="b"))
    db.commit()
    versione = esce.token_version

    r = disattiva_utente(db, esce)
    db.commit()
    db.expire_all()
    assert r["posti_liberati"] == 1 and esce.is_active is False and esce.token_version == versione + 1
    stati = {i.user_id: i.stato for i in db.query(Iscrizione).all()}
    assert stati[esce.id] == S.annullato and stati[attende.id] == S.iscritto
    assert db.query(PushSubscription).count() == 0


def test_lo_storico_formativo_resta(db, crea_utente, crea_corso, crea_edizione, crea_iscrizione):
    u = crea_utente("storico@test.it")
    chiusa = crea_edizione(crea_corso())
    fatta = crea_iscrizione(chiusa, u, S.completato, giorni_fa=30)
    disattiva_utente(db, u)
    db.commit()
    db.refresh(fatta)
    assert fatta.stato == S.completato and fatta.completato_at is not None


def test_avvisi_per_docente_e_responsabile(db, crea_utente, crea_corso, crea_edizione, crea_ufficio):
    u = crea_utente("capo@test.it")
    ed = crea_edizione(crea_corso(), stato=StatoEdizione.pianificata)
    db.add(EdizioneDocente(edizione_id=ed.id, user_id=u.id, ruolo=RuoloDocente.titolare))
    db.commit()
    crea_ufficio("Ufficio Acquisti", responsabile=u)
    r = disattiva_utente(db, u)
    assert u.is_active is False  # l'account si chiude comunque
    assert any("docente di 1" in a for a in r["avvisi"]) and any("Ufficio Acquisti" in a for a in r["avvisi"])


# --- piano ---------------------------------------------------------------------------------

def test_piano_crea_aggiorna_disattiva_riattiva(db, entra, crea_utente):
    crea_utente("resta@az.it", full_name="Vecchio Nome")
    crea_utente("esce@az.it")
    crea_utente("disabilitato@az.it")
    crea_utente("tornato@az.it", is_active=False)
    crea_utente("esterno@az.it", is_external=True)          # mai toccato
    crea_utente("altro@altrodominio.it")                    # fuori dai domini del gruppo: mai toccato
    entra.membri = [membro("resta@az.it", "Nuovo Nome"), membro("nuovo@az.it", "Persona Nuova"),
                    membro("disabilitato@az.it", attivo=False), membro("tornato@az.it", "Tornato")]
    piano = svc.calcola_piano(db, svc.leggi_membri())
    assert [c["email"] for c in piano["crea"]] == ["nuovo@az.it"]
    assert [a["email"] for a in piano["aggiorna"]] == ["resta@az.it"]
    assert {d["email"]: d["motivo"] for d in piano["disattiva"]} == {
        "esce@az.it": "non più nel gruppo Entra", "disabilitato@az.it": "account disabilitato in Entra"}
    assert [r["email"] for r in piano["riattiva"]] == ["tornato@az.it"]
    assert piano["freno"] is None


def test_admin_tecnico_non_si_disattiva_mai_da_solo(db, entra, crea_utente):
    crea_utente("capo@az.it", UserRole.admin_tecnico)
    entra.membri = [membro("qualcuno@az.it")]
    piano = svc.calcola_piano(db, svc.leggi_membri())
    assert piano["disattiva"] == [] and piano["esclusi"][0]["email"] == "capo@az.it"


def test_freno_se_le_disattivazioni_sono_troppe(db, entra, crea_utente):
    for n in range(10):
        crea_utente(f"p{n}@az.it")
    entra.membri = [membro("p0@az.it")]  # gruppo svuotato per errore: 9 uscite su 10
    assert svc.calcola_piano(db, svc.leggi_membri())["freno"]


def test_solo_i_nuovi_assunti_attivano_i_percorsi_d_ingresso(db, entra):
    from datetime import datetime, timedelta, timezone
    ora = datetime.now(timezone.utc)
    entra.membri = [membro("nuovo@az.it", assunto=ora - timedelta(days=10)), membro("storico@az.it", assunto=ora - timedelta(days=3000)),
                    membro("senzadata@az.it")]
    crea = {c["email"]: c["data_ingresso"] for c in svc.calcola_piano(db, svc.leggi_membri())["crea"]}
    assert crea["nuovo@az.it"] is not None and crea["storico@az.it"] is None and crea["senzadata@az.it"] is None


# --- applicazione e automatismo ----------------------------------------------------------

def test_applica_il_piano_e_traccia_ogni_modifica(db, entra, crea_utente):
    crea_utente("resta@az.it", full_name="Vecchio")
    crea_utente("esce@az.it")
    entra.membri = [membro("resta@az.it", "Nuovo"), membro("nuovo@az.it", "Persona Nuova")]
    esito = svc.applica_piano(db, svc.calcola_piano(db, svc.leggi_membri()))
    assert (esito["creati"], esito["aggiornati"], esito["disattivati"]) == (1, 1, 1)
    db.expire_all()
    assert db.query(User).filter(User.email_idx == impronta("esce@az.it")).one().is_active is False
    nuovo = db.query(User).filter(User.email_idx == impronta("nuovo@az.it")).one()
    assert nuovo.origine_credenziali == "dominio" and nuovo.role == UserRole.user and nuovo.is_active
    azioni = {a.action for a in db.query(AuditLog).all()}
    assert {"CREATE", "UPDATE", "DISATTIVA_UTENTE"} <= azioni


def test_riattivazione_solo_se_richiesta(db, entra, crea_utente):
    crea_utente("tornato@az.it", is_active=False)
    entra.membri = [membro("tornato@az.it", "Tornato")]
    piano = svc.calcola_piano(db, svc.leggi_membri())
    assert svc.applica_piano(db, piano)["riattivati"] == 0
    assert svc.applica_piano(db, piano, riattiva=True)["riattivati"] == 1


def test_giro_automatico_applica_e_avvisa(db, entra, crea_utente, admin):
    crea_utente("a@az.it")
    esce = crea_utente("esce@az.it")
    crea_utente("tornato@az.it", is_active=False)
    entra.membri = [membro("a@az.it", "Utente Test"), membro("tornato@az.it")] + [membro(f"x{n}@az.it") for n in range(3)]
    risultato = svc.sincronizza_automatico(db)
    assert "disattivati 1" in risultato
    db.expire_all()
    assert esce.is_active is False
    assert db.query(User).filter(User.email_idx == impronta("tornato@az.it")).one().is_active is False  # l'automatico non riattiva
    assert db.query(Notification).filter(Notification.tipo == "sync_entra", Notification.user_id == admin.id).count() == 1  # c'e' una riattivazione da valutare


def test_giro_automatico_si_ferma_davanti_a_un_piano_sospetto(db, entra, crea_utente, admin):
    utenti = [crea_utente(f"p{n}@az.it") for n in range(10)]
    entra.membri = [membro("p0@az.it", "Utente Test")]
    risultato = svc.sincronizza_automatico(db)
    assert risultato.startswith("sospesa")
    db.expire_all()
    assert all(u.is_active for u in utenti)
    assert db.query(Notification).filter(Notification.tipo == "sync_entra").count() >= 1


def test_il_giro_automatico_e_tracciato_come_job(db, entra, crea_utente):
    crea_utente("esce@az.it"); crea_utente("resta@az.it")
    entra.membri = [membro("resta@az.it")]
    esegui_tracciato("sync_entra", svc.sincronizza_automatico)
    run = db.query(JobRun).filter(JobRun.job_id == "sync_entra").one()
    assert run.esito == "ok" and "disattivati" in run.dettaglio


def test_errore_di_graph_e_registrato_e_non_blocca(db, entra):
    entra.errore = "Graph ha risposto 403"
    esegui_tracciato("sync_entra", svc.sincronizza_automatico)
    run = db.query(JobRun).filter(JobRun.job_id == "sync_entra").one()
    assert run.esito == "errore" and "403" in run.errore


# --- API -----------------------------------------------------------------------------------

def test_api_non_configurata(client, admin, auth):
    assert client.post("/api/admin/entra/anteprima", headers=auth(admin)).status_code == 400
    assert client.get("/api/admin/entra/stato", headers=auth(admin)).json()["configurato"] is False


def test_api_solo_admin_tecnico(client, formazione, utente, auth, entra):
    for persona in (formazione, utente):
        assert client.post("/api/admin/entra/anteprima", headers=auth(persona)).status_code == 403
        assert client.post("/api/admin/entra/applica", headers=auth(persona)).status_code == 403


def test_api_anteprima_non_modifica_e_applica_si(client, db, admin, auth, entra, crea_utente):
    esce = crea_utente("esce@az.it")
    entra.membri = [membro("admin@test.it", "Admin Test"), membro("nuovo@az.it", "Nuovo")]
    anteprima = client.post("/api/admin/entra/anteprima", headers=auth(admin)).json()
    assert [d["email"] for d in anteprima["disattiva"]] == ["esce@az.it"]
    db.refresh(esce)
    assert esce.is_active is True and db.query(User).filter(User.email_idx == impronta("nuovo@az.it")).count() == 0
    r = client.post("/api/admin/entra/applica", headers=auth(admin), params={"impronta": anteprima["impronta"]})
    assert r.status_code == 200 and r.json()["disattivati"] == 1
    db.expire_all()
    assert esce.is_active is False
    assert db.query(AuditLog).filter(AuditLog.action == "SYNC_ENTRA").count() == 1


def test_api_applica_rifiuta_un_piano_sospetto_senza_conferma(client, db, admin, auth, entra, crea_utente):
    utenti = [crea_utente(f"p{n}@az.it") for n in range(10)]
    entra.membri = [membro("p0@az.it", "Utente Test")]
    impronta = client.post("/api/admin/entra/anteprima", headers=auth(admin)).json()["impronta"]
    assert client.post("/api/admin/entra/applica", headers=auth(admin), params={"impronta": impronta}).status_code == 409
    db.expire_all()
    assert all(u.is_active for u in utenti)
    assert client.post("/api/admin/entra/applica", headers=auth(admin), params={"forza": "true", "impronta": impronta}).status_code == 200


def test_applica_rifiuta_un_piano_diverso_da_quello_visto(client, admin, auth, entra, crea_utente):
    crea_utente("esce@az.it"); crea_utente("resta@az.it")
    entra.membri = [membro("admin@test.it", "Admin Test"), membro("resta@az.it", "Resta")]
    impronta = client.post("/api/admin/entra/anteprima", headers=auth(admin)).json()["impronta"]
    entra.membri = [membro("admin@test.it", "Admin Test")]  # nel frattempo esce anche un'altra persona
    r = client.post("/api/admin/entra/applica", headers=auth(admin), params={"impronta": impronta})
    assert r.status_code == 412
    assert client.post("/api/admin/entra/applica", headers=auth(admin)).status_code == 412  # senza impronta nemmeno


def test_l_impronta_cambia_se_cambia_il_nome_dopo_l_anteprima(client, admin, auth, entra, crea_utente):
    crea_utente("resta@az.it")
    entra.membri = [membro("admin@test.it", "Admin Test"), membro("resta@az.it", "Nome vecchio")]
    impronta = client.post("/api/admin/entra/anteprima", headers=auth(admin)).json()["impronta"]
    entra.membri = [membro("admin@test.it", "Admin Test"), membro("resta@az.it", "Nome nuovo")]  # stessa persona, stessa azione, valore diverso
    assert client.post("/api/admin/entra/applica", headers=auth(admin), params={"impronta": impronta}).status_code == 412


def test_api_graph_irraggiungibile(client, admin, auth, entra):
    entra.errore = "autenticazione Graph rifiutata (401)"
    assert client.post("/api/admin/entra/anteprima", headers=auth(admin)).status_code == 502


def test_import_cessati_csv_usa_lo_stesso_offboarding(client, db, admin, auth, crea_utente, crea_corso, crea_edizione, crea_iscrizione):
    esce = crea_utente("cessato@az.it")
    ed = crea_edizione(crea_corso(), stato=StatoEdizione.pianificata)
    i = crea_iscrizione(ed, esce)
    r = client.post("/api/auth/users/import-csv", headers=auth(admin), params={"modo": "cessati"}, files={"file": ("elenco.csv", b"email\ncessato@az.it\n", "text/csv")})
    assert r.status_code == 200 and r.json()["righe"][0]["esito"] == "disattivato"
    db.expire_all()
    assert esce.is_active is False and db.query(Iscrizione).filter(Iscrizione.id == i.id).one().stato == S.annullato
