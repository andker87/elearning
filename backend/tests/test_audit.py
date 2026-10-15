"""Audit log: cosa viene registrato, filtri, export, IP reale."""
from app.config import settings
from app.models.audit import AuditLog

from conftest import PASSWORD


def test_login_registra_l_ip_dietro_un_proxy_fidato(client, db, utente, monkeypatch):
    monkeypatch.setattr(settings, "PROXY_FIDUCIARI", "172.16.0.0/12")
    monkeypatch.setattr(settings, "PROXY_CLOUDFLARE", True)
    client.post("/api/auth/login", json={"email": utente.email, "password": PASSWORD},
                headers={"X-Real-IP": "172.27.0.1", "CF-Connecting-IP": "203.0.113.7", "X-Forwarded-For": "10.0.0.1"})
    riga = db.query(AuditLog).filter(AuditLog.action == "LOGIN").one()
    assert riga.ip_address == "203.0.113.7" and riga.user_email == utente.email


def test_login_fallito_registrato_senza_utente(client, db):
    client.post("/api/auth/login", json={"email": "ignoto@test.it", "password": "x"})
    riga = db.query(AuditLog).filter(AuditLog.action == "LOGIN_FAILED").one()
    assert riga.user_id is None and "ignoto@test.it" in riga.detail


def test_filtri_dell_elenco(client, admin, utente, auth):
    client.post("/api/auth/login", json={"email": utente.email, "password": PASSWORD})
    client.post("/api/auth/login", json={"email": utente.email, "password": "sbagliata"})
    voci = lambda **p: client.get("/api/admin/audit", headers=auth(admin), params=p).json()
    assert {v["action"] for v in voci()["items"]} == {"LOGIN", "LOGIN_FAILED"}
    assert [v["action"] for v in voci(action="LOGIN")["items"]] == ["LOGIN"]
    assert voci(utente=utente.email)["totale"] == 1  # il tentativo fallito non ha utente associato
    assert voci(q="sbagliata")["totale"] == 0 and voci(q=utente.email)["totale"] == 2
    assert voci(da="2999-01-01")["totale"] == 0
    assert voci(a="2000-01-01")["totale"] == 0
    opzioni = client.get("/api/admin/audit/filtri", headers=auth(admin)).json()
    assert "LOGIN" in opzioni["azioni"]


def test_paginazione(client, db, admin, auth):
    for n in range(7):
        db.add(AuditLog(action="PROVA", user_email="x@test.it", detail=str(n)))
    db.commit()
    r = client.get("/api/admin/audit", headers=auth(admin), params={"action": "PROVA", "per_pagina": 3, "pagina": 3}).json()
    assert r["totale"] == 7 and len(r["items"]) == 1


def test_export_con_gli_stessi_filtri(client, db, admin, auth):
    db.add_all([AuditLog(action="A1", user_email="x@test.it"), AuditLog(action="B2", user_email="x@test.it")])
    db.commit()
    csv_ = client.get("/api/admin/audit/export", headers=auth(admin), params={"action": "A1"}).text
    assert "A1" in csv_ and "B2" not in csv_
    assert client.get("/api/admin/audit/export", headers=auth(admin), params={"formato": "xlsx"}).status_code == 200


def test_cambio_password_e_blocco_lasciano_traccia(client, db, utente, auth):
    for _ in range(5):
        client.post("/api/auth/login", json={"email": utente.email, "password": "x"})
    assert db.query(AuditLog).filter(AuditLog.action == "ACCOUNT_BLOCCATO").count() == 1


# --- IP del client: gli header si credono solo se arrivano da un proxy dichiarato ---------------

def richiesta(peer, **header):
    from starlette.requests import Request
    intestazioni = [(k.replace("_", "-").lower().encode(), v.encode()) for k, v in header.items()]
    return Request({"type": "http", "headers": intestazioni, "client": (peer, 1234), "method": "GET", "path": "/", "query_string": b""})


def test_senza_proxy_fidati_gli_header_si_ignorano(monkeypatch):
    from app.services.audit import ip_client
    monkeypatch.setattr(settings, "PROXY_FIDUCIARI", "")
    r = richiesta("172.27.0.1", x_real_ip="198.51.100.9", cf_connecting_ip="1.2.3.4", x_forwarded_for="5.6.7.8")
    assert ip_client(r) == "198.51.100.9"           # chi si connette davvero (scritto da nginx), non quello che dice il client
    assert ip_client(richiesta("192.168.1.50", cf_connecting_ip="1.2.3.4")) == "192.168.1.50"


def test_proxy_fidato_cloudflare_e_catena_forwarded(monkeypatch):
    from app.services.audit import ip_client
    monkeypatch.setattr(settings, "PROXY_FIDUCIARI", "10.0.0.0/8, 192.168.1.5")
    monkeypatch.setattr(settings, "PROXY_CLOUDFLARE", True)
    assert ip_client(richiesta("10.1.1.1", x_real_ip="10.1.1.1", cf_connecting_ip="203.0.113.7")) == "203.0.113.7"
    monkeypatch.setattr(settings, "PROXY_CLOUDFLARE", False)
    # il client aggiunge un valore falso a sinistra: la catena si legge da destra e ci si ferma al primo non fidato
    catena = "9.9.9.9, 203.0.113.50, 10.2.2.2"
    assert ip_client(richiesta("10.1.1.1", x_real_ip="10.1.1.1", x_forwarded_for=catena)) == "203.0.113.50"
    # un proxy fidato che non dice nulla: resta il suo indirizzo
    assert ip_client(richiesta("10.1.1.1", x_real_ip="10.1.1.1")) == "10.1.1.1"


def test_valori_non_validi_non_fanno_danni(monkeypatch):
    from app.services.audit import ip_client
    monkeypatch.setattr(settings, "PROXY_FIDUCIARI", "10.0.0.0/8, non-una-rete")
    monkeypatch.setattr(settings, "PROXY_CLOUDFLARE", True)
    assert ip_client(richiesta("10.1.1.1", x_real_ip="10.1.1.1", cf_connecting_ip="<script>", x_forwarded_for="boh, 203.0.113.9")) == "203.0.113.9"
    assert ip_client(None) is None


def test_il_limite_di_login_non_si_aggira_cambiando_header(client, monkeypatch):
    monkeypatch.setattr(settings, "PROXY_FIDUCIARI", "")
    codici = [client.post("/api/auth/login", json={"email": f"x{i}@test.it", "password": "x"},
                          headers={"X-Forwarded-For": f"203.0.113.{i}", "CF-Connecting-IP": f"198.51.100.{i}"}).status_code for i in range(32)]
    assert codici[:30] == [401] * 30 and codici[30] == 429



def test_con_un_proxy_aziendale_cf_connecting_ip_si_ignora(monkeypatch):
    """Un proxy fidato che non e' Cloudflare lascerebbe passare quell'header cosi' come lo manda il client."""
    from app.services.audit import ip_client
    monkeypatch.setattr(settings, "PROXY_FIDUCIARI", "10.0.0.0/8")
    monkeypatch.setattr(settings, "PROXY_CLOUDFLARE", False)
    r = richiesta("10.1.1.1", x_real_ip="10.1.1.1", cf_connecting_ip="6.6.6.6", x_forwarded_for="203.0.113.20")
    assert ip_client(r) == "203.0.113.20"
