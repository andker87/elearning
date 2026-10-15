"""Registro attivita' (1.9.1): livelli, riepilogo, esportazione giornaliera, conservazione, indici."""
import json
import os
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa

from app.config import settings
from app.models.audit import AuditLog
from app.services import audit_manutenzione as man


def _evento(db, azione, giorni_fa=0, email="x@test.it"):
    e = AuditLog(action=azione, user_email=email, created_at=datetime.now(timezone.utc) - timedelta(days=giorni_fa, hours=1))
    db.add(e); db.commit()
    return e


def test_di_default_solo_importanti_e_tutti_su_richiesta(client, auth, admin, db):
    _evento(db, "LOGIN"); _evento(db, "LOGIN_FAILED"); _evento(db, "UPDATE"); _evento(db, "VIDEO_AVVIATO")
    r = client.get("/api/admin/audit", headers=auth(admin)).json()
    assert {x["action"] for x in r["items"]} == {"LOGIN_FAILED", "UPDATE"}
    r = client.get("/api/admin/audit?livello=tutti", headers=auth(admin)).json()
    assert r["totale"] == 4
    # scegliendo l'azione si vede anche se di routine
    assert client.get("/api/admin/audit?action=LOGIN", headers=auth(admin)).json()["totale"] == 1


def test_export_rispetta_il_livello(client, auth, admin, db):
    _evento(db, "LOGIN"); _evento(db, "DELETE")
    csv = client.get("/api/admin/audit/export?formato=csv", headers=auth(admin)).text
    assert "DELETE" in csv and "LOGIN" not in csv
    assert "LOGIN" in client.get("/api/admin/audit/export?formato=csv&livello=tutti", headers=auth(admin)).text


def test_riepilogo_conta_per_periodo(client, auth, admin, db):
    _evento(db, "LOGIN"); _evento(db, "LOGIN_FAILED"); _evento(db, "LOGIN_FAILED"); _evento(db, "UPDATE", giorni_fa=3); _evento(db, "ACCOUNT_BLOCCATO")
    r = client.get("/api/admin/audit/riepilogo", headers=auth(admin)).json()
    p = r["periodi"]
    assert p["24 ore"]["accessi"] == 1 and p["24 ore"]["accessi_falliti"] == 2 and p["24 ore"]["account_bloccati"] == 1
    assert p["24 ore"]["importanti"] == 3 and p["7 giorni"]["importanti"] == 4 and p["7 giorni"]["totali"] == 5
    assert r["conservazione_mesi"] == 24 and r["esportazione_attiva"] is False


def test_riepilogo_solo_admin_tecnico(client, auth, formazione):
    assert client.get("/api/admin/audit/riepilogo", headers=auth(formazione)).status_code == 403


def test_esportazione_giornaliera_scrive_i_giorni_passati_una_volta(db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "AUDIT_EXPORT_DIR", str(tmp_path))
    _evento(db, "UPDATE", giorni_fa=2); _evento(db, "LOGIN", giorni_fa=2); _evento(db, "DELETE", giorni_fa=1); _evento(db, "CREATE", giorni_fa=0)
    assert man.esporta_giorni_trascorsi(db) == 2          # oggi non si esporta: il giorno non e' finito
    file = sorted(os.listdir(tmp_path))
    assert len(file) == 2 and all(f.endswith(".ndjson") for f in file)
    righe = [json.loads(l) for l in open(tmp_path / file[0], encoding="utf-8")]
    assert {r["azione"] for r in righe} == {"UPDATE", "LOGIN"} and righe[0]["utente"] == "x@test.it"
    assert man.esporta_giorni_trascorsi(db) == 0          # niente di nuovo: i file non si riscrivono
    assert not [f for f in os.listdir(tmp_path) if f.endswith(".parte")]


def test_pulizia_cancella_oltre_la_conservazione(db, monkeypatch):
    monkeypatch.setattr(settings, "AUDIT_EXPORT_DIR", None)
    monkeypatch.setattr(settings, "AUDIT_RETENZIONE_MESI", 1)
    _evento(db, "UPDATE", giorni_fa=90); _evento(db, "UPDATE", giorni_fa=40); _evento(db, "UPDATE", giorni_fa=5)
    assert man.pulisci_vecchi(db) == 2
    assert db.query(AuditLog).count() == 1


def test_conservazione_zero_non_cancella_nulla(db, monkeypatch):
    monkeypatch.setattr(settings, "AUDIT_RETENZIONE_MESI", 0)
    _evento(db, "UPDATE", giorni_fa=4000)
    assert man.pulisci_vecchi(db) == 0 and db.query(AuditLog).count() == 1


def test_con_esportazione_attiva_non_si_cancella_cio_che_non_e_esportato(db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "AUDIT_EXPORT_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "AUDIT_RETENZIONE_MESI", 1)
    _evento(db, "UPDATE", giorni_fa=90)
    assert man.pulisci_vecchi(db) == 0                    # nessun file del giorno: si aspetta
    man.esporta_giorni_trascorsi(db)
    assert man.pulisci_vecchi(db) == 1


def test_manutenzione_lascia_traccia_della_pulizia(db, monkeypatch):
    monkeypatch.setattr(settings, "AUDIT_EXPORT_DIR", None)
    monkeypatch.setattr(settings, "AUDIT_RETENZIONE_MESI", 1)
    _evento(db, "UPDATE", giorni_fa=90)
    assert "cancellati: 1" in man.manutenzione(db)
    assert [r.action for r in db.query(AuditLog).all()] == ["AUDIT_PULIZIA"]


def test_copia_in_tempo_reale_solo_dopo_il_commit(client, auth, admin, db, monkeypatch, capsys):
    monkeypatch.setattr(settings, "AUDIT_LOG_STDOUT", True)
    from app.services import audit
    audit.log_from_request(db, None, admin, "PROVA_ANNULLATA"); db.rollback()
    audit.log_from_request(db, None, admin, "PROVA_CONFERMATA"); db.commit()
    out = capsys.readouterr().out
    assert "PROVA_CONFERMATA" in out and "PROVA_ANNULLATA" not in out
    riga = [l for l in out.splitlines() if l.startswith("AUDIT ")][0]
    assert json.loads(riga[6:])["utente"] == admin.email


def test_indici_presenti_dopo_le_migrazioni(db):
    nomi = {i["name"] for i in sa.inspect(db.get_bind()).get_indexes("audit_log")}
    assert {"ix_audit_log_created_at", "ix_audit_log_action_created_at"} <= nomi
