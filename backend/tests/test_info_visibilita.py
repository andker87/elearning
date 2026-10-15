"""Pagina Info (1.9.2): agli utenti solo nome e versione, i dettagli tecnici all'Admin tecnico."""
from app.version import APP_VERSION

TECNICI = ("changelog", "ambiente", "dipendenze", "integrazioni")


def test_utente_e_formazione_vedono_solo_nome_e_versione(client, auth, utente, formazione):
    for chi in (utente, formazione):
        d = client.get("/api/about", headers=auth(chi)).json()
        assert d["versione"] == APP_VERSION and d["nome_piattaforma"]
        assert not any(k in d for k in TECNICI)


def test_admin_tecnico_vede_tutto(client, auth, admin):
    d = client.get("/api/about", headers=auth(admin)).json()
    assert all(k in d for k in TECNICI) and d["changelog"][0]["version"] == APP_VERSION


def test_senza_accesso_niente(client):
    assert client.get("/api/about").status_code in (401, 403)
